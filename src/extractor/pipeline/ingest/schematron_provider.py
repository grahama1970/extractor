"""
Schematron HTML Provider
-----------------------
HTML-to-JSON extraction via local Ollama (dev) or SGLang (prod) with self-correction.

ALL LLM calls routed through /scillm (LiteLLM wrapper) — never raw httpx.

Dual deployment:
  Dev  (A5000 24GB): Ollama on port 11434 — multi-model, KV cache offloads to RAM
  Prod (H200 cluster): SGLang on port 30001 — continuous batching, LoRA hot-swap

Model: hf.co/debaasvan/Schematron-3B-Q4_K_M-GGUF (Ollama) or inference-net/schematron-3b (SGLang/inference.net)
       Purpose-built for HTML→schema-conforming JSON extraction.
       Based on Llama-3.2-3B-Instruct, 4.41 LLM-judge score.
       Quality gap vs 8B (4.64) closeable with /prompt-lab self-improvement.

Env vars: SCHEMATRON_API_BASE (default: http://localhost:11434 for Ollama)
          SCHEMATRON_API_KEY (optional, for inference.net or authenticated endpoints)
          SCHEMATRON_MODEL (default: hf.co/debaasvan/Schematron-3B-Q4_K_M-GGUF:latest)
          SCHEMATRON_PROVIDER (optional: "ollama" or "openai_like", auto-detected from base URL)

NOTE: Schematron models REQUIRE response_format with json_schema.
      Ollama supports this via compatibility layer (translates to native format param).

Falls back to native HTMLProvider (BeautifulSoup + markdownify) when
API is unavailable or returns invalid output after self-correction.
"""

from __future__ import annotations

import asyncio
import json
import base64
import io
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal, Union
from urllib.parse import urlparse

import httpx
import pandas as pd
import jsonschema
from PIL import Image
from bs4 import BeautifulSoup, Comment
from loguru import logger
import trafilatura
from pydantic import BaseModel
from scillm import completion

# Internal imports from extractor core
from extractor.core.schema.unified_document import (
    UnifiedDocument,
    SourceType,
    BaseBlock,
    BlockType,
    BlockMetadata,
    DocumentMetadata,
    TableBlock,
    TableCell,
    ImageBlock,
    HierarchyNode,
)


# --- 1. The Schema (Simplified UnifiedDocument for LLM) ---

UNIFIED_DOC_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["heading", "paragraph", "table", "image", "list", "code"]
                    },
                    "content": {
                        "type": ["string", "object"],
                        "description": "Text content, or table object, or image description."
                    },
                    "metadata": {"type": "object"}
                },
                "required": ["type", "content"]
            }
        }
    },
    "required": ["blocks"]
}


# --- 2. Helper Classes & Functions ---

class SchematronConfig(BaseModel):
    # Dev: Ollama on localhost:11434 (multi-model, KV cache offload to RAM)
    # Prod: SGLang on localhost:30001 (continuous batching, LoRA hot-swap)
    # Override: SCHEMATRON_API_BASE env var
    api_base: str = os.getenv("SCHEMATRON_API_BASE", "http://localhost:11434")
    api_key: Optional[str] = os.getenv("SCHEMATRON_API_KEY", os.getenv("INFERENCE_API_KEY"))
    model: str = os.getenv("SCHEMATRON_MODEL", "hf.co/debaasvan/Schematron-3B-Q4_K_M-GGUF:latest")
    # scillm provider: "ollama" for Ollama, "openai_like" for SGLang/inference.net
    # Auto-detected from api_base if not set
    provider: Optional[str] = os.getenv("SCHEMATRON_PROVIDER")
    vision_enabled: bool = True
    vision_api_base: Optional[str] = os.getenv("CHUTES_API_BASE") or os.getenv("OPENAI_API_BASE")
    vision_api_key: Optional[str] = os.getenv("CHUTES_API_KEY") or os.getenv("OPENAI_API_KEY")
    vision_model: str = os.getenv("CHUTES_VLM_MODEL") or "gpt-4o-mini"
    max_attempts: int = 3
    timeout_s: float = 120.0
    debug_dir: Optional[Path] = None

    def detect_provider(self) -> str:
        """Auto-detect scillm provider from api_base URL.

        Always uses 'openai_like' — works with Ollama /v1, SGLang, inference.net.
        The native 'ollama' provider uses /api/generate which has model name
        compatibility issues with GGUF models from HuggingFace.
        """
        if self.provider:
            return self.provider
        # openai_like works for all backends (Ollama /v1, SGLang, inference.net)
        return "openai_like"

    def get_api_base(self) -> str:
        """Return api_base with /v1 suffix for openai_like provider."""
        base = self.api_base.rstrip("/")
        provider = self.detect_provider()
        if provider == "openai_like" and not base.endswith("/v1"):
            return f"{base}/v1"
        return base


def clean_html_for_llm(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
        tag.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    return str(soup)


def extract_tables_pd(html: str) -> List[Dict[str, Any]]:
    try:
        dfs = pd.read_html(html)
    except ValueError:
        return []
    except Exception as e:
        logger.warning(f"pandas tables failed: {e}")
        return []

    out = []
    for i, df in enumerate(dfs):
        # Basic serialization
        out.append({
            "index": i,
            "columns": df.columns.astype(str).tolist(),
            "data": df.astype(object).where(pd.notnull(df), None).values.tolist()
        })
    return out


async def batch_vision_ocr(
    images: List[Dict],
    config: SchematronConfig
) -> Dict[str, str]:
    """
    Batched vision extraction via scillm. images = [{id, bytes, alt}]
    Returns {id: text}
    """
    if not (config.vision_api_base and config.vision_api_key):
        return {}

    from scillm import acompletion

    results = {}

    async def _process_one(img):
        try:
            b64 = base64.b64encode(img["bytes"]).decode("utf-8")
            resp = await acompletion(
                model=config.vision_model,
                api_base=config.vision_api_base,
                api_key=config.vision_api_key,
                custom_llm_provider="openai_like",
                messages=[
                    {"role": "user", "content": [
                        {"type": "text", "text": "Extract all text from this image. Output text only."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                    ]}
                ],
                max_tokens=1000,
                timeout=60.0,
            )
            results[img["id"]] = resp.choices[0].message.content
        except Exception as e:
            logger.warning(f"Vision failed for {img['id']}: {e}")

    await asyncio.gather(*[_process_one(img) for img in images])

    return results


# --- 3. The Provider ---

class SchematronHTMLProvider:
    """
    Ingests HTML using Schematron3B to produce a UnifiedDocument.
    """
    def __init__(self, file_path: Optional[Union[str, Path]] = None, config: Optional[Dict[str, Any]] = None):
        # Support both registry pattern (init with config, then call extract_document)
        # and direct init pattern.
        self.config = config or {}
        # Convert dict config to pydantic model if needed, or just use defaults
        self.schematron_config = SchematronConfig(**{k: v for k, v in self.config.items() if k in SchematronConfig.model_fields})
        
        if file_path:
            self.file_path = Path(file_path)
        else:
            self.file_path = None

    def extract_document(self, filepath: Optional[Union[str, Path]] = None) -> UnifiedDocument:
        """Standard registry interface."""
        if filepath:
            self.file_path = Path(filepath)
            
        if not self.file_path:
            raise ValueError("No file path provided")
            
        return self.parse()

    def parse(self) -> UnifiedDocument:
        logger.info(f"SchematronHTMLProvider parsing {self.file_path}")
        
        # 1. Load & Clean
        raw_html = self.file_path.read_text(errors="replace")
        cleaned_html = clean_html_for_llm(raw_html)
        
        # 2. Extract Context (Tables)
        tables_ctx = extract_tables_pd(cleaned_html)
        
        # 3. Extract Context (Images/Vision)
        media_ctx = []
        if self.schematron_config.vision_enabled:
            # (Simplified image discovery logic)
            soup = BeautifulSoup(cleaned_html, "lxml")
            imgs_to_process = []
            
            for img in soup.find_all("img"):
                src = img.get("src")
                if not src: continue
                # Resolve local path
                if not src.startswith("http"):
                    local_p = (self.file_path.parent / src).resolve()
                    if local_p.exists():
                        try:
                            b = local_p.read_bytes()
                            imgs_to_process.append({
                                "id": str(local_p),
                                "bytes": b,
                                "alt": img.get("alt", "")
                            })
                        except Exception as e:
                            logger.debug(f"Failed to read image {local_p}: {e}")
            
            if imgs_to_process:
                logger.info(f"Running vision OCR on {len(imgs_to_process)} local images")
                ocr_results = asyncio.run(batch_vision_ocr(imgs_to_process, self.schematron_config))
                
                for img in imgs_to_process:
                    txt = ocr_results.get(img["id"])
                    if txt:
                        media_ctx.append({
                            "src": img["id"],
                            "alt": img["alt"],
                            "extracted_text": txt
                        })

        # 4. Schematron Inference Loop
        json_output = self._run_inference_loop(cleaned_html, tables_ctx, media_ctx)
        
        # 5. Manifest as UnifiedDocument
        return self._manifest_document(json_output)

    def _build_strict_schema(self) -> dict:
        """Build a strict JSON schema for inference.net's response_format.

        inference.net requires additionalProperties=false and all properties
        listed in required. This is a stricter version of UNIFIED_DOC_SCHEMA.
        """
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "blocks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["heading", "paragraph", "table", "image", "list", "code"],
                            },
                            "content": {"type": "string"},
                            "level": {"type": ["integer", "null"]},
                            "rows": {
                                "type": ["array", "null"],
                                "items": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                        "required": ["type", "content", "level", "rows"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["title", "blocks"],
            "additionalProperties": False,
        }

    def _check_api_available(self) -> bool:
        """Pre-flight check: is the Schematron API reachable?

        Uses a lightweight httpx GET to /api/tags (Ollama) or /v1/models (OpenAI-like).
        This is the one place we use raw httpx — scillm doesn't expose a health check.
        """
        try:
            base = self.schematron_config.api_base.rstrip("/")
            provider = self.schematron_config.detect_provider()
            if provider == "ollama":
                health_url = f"{base}/api/tags"
            else:
                health_url = f"{base}/v1/models" if not base.endswith("/v1") else f"{base}/models"
            headers = {}
            if self.schematron_config.api_key:
                headers["Authorization"] = f"Bearer {self.schematron_config.api_key}"
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(health_url, headers=headers)
                resp.raise_for_status()
                return True
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            logger.warning(f"Schematron API not available at {self.schematron_config.api_base}: {e}")
            return False

    def _run_inference_loop(self, html: str, tables: List[Dict], media: List[Dict]) -> Dict[str, Any]:
        """Self-correction loop via scillm (Ollama dev / SGLang prod / inference.net).

        Each retry appends the previous error to the prompt so the model
        can correct its output. Differentiates between connection errors
        (immediate fallback) and output errors (correctable via retry).

        All LLM calls routed through scillm — never raw httpx.
        """
        # Pre-flight: check if API is reachable before wasting time
        if not self._check_api_available():
            raise ConnectionError(
                f"Schematron API not reachable at {self.schematron_config.api_base}. "
                f"Check SCHEMATRON_API_BASE env var and network connectivity."
            )

        system_prompt = (
            "You are a document extraction engine. "
            "Convert the HTML content into a structured JSON document. "
            "Use the provided schema. The 'blocks' array should contain the document flow. "
            "Prefer the provided DETERMINISTIC TABLES and MEDIA TEXT over raw HTML parsing where possible. "
            "Output ONLY valid JSON — no markdown fences, no explanation."
        )

        user_content = "\n".join([
            "### JSON SCHEMA",
            json.dumps(UNIFIED_DOC_SCHEMA, indent=2),
            "\n### CONTEXT: TABLES",
            json.dumps(tables, indent=2),
            "\n### CONTEXT: IMAGES/OCR",
            json.dumps(media, indent=2),
            "\n### HTML CONTENT",
            html[:200000],  # Cap context
        ])

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        prior_errors: List[str] = []
        provider = self.schematron_config.detect_provider()

        # Schematron models require response_format with json_schema
        response_format = None
        if "schematron" in self.schematron_config.model.lower():
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "html_extraction",
                    "strict": True,
                    "schema": self._build_strict_schema(),
                }
            }

        for attempt in range(self.schematron_config.max_attempts):
            # On retry, append correction context from previous failure
            if prior_errors:
                correction = (
                    f"Your previous attempt (attempt {attempt}) produced invalid output. "
                    f"Error: {prior_errors[-1]}. "
                    f"Fix the error and output ONLY valid JSON matching the schema."
                )
                messages.append({"role": "user", "content": correction})

            try:
                # Route through scillm — handles Ollama, SGLang, inference.net
                kwargs = {
                    "model": self.schematron_config.model,
                    "messages": messages,
                    "api_base": self.schematron_config.get_api_base(),
                    "custom_llm_provider": provider,
                    "temperature": 0.0,
                    "max_tokens": 16000,
                    "timeout": self.schematron_config.timeout_s,
                }
                if self.schematron_config.api_key:
                    kwargs["api_key"] = self.schematron_config.api_key
                if response_format:
                    kwargs["response_format"] = response_format

                resp = completion(**kwargs)
                raw = resp.choices[0].message.content

            except Exception as e:
                error_str = str(e).lower()
                # Connection errors = API down, don't retry blindly
                if any(k in error_str for k in ("connect", "refused", "unreachable")):
                    raise ConnectionError(
                        f"Schematron API connection lost on attempt {attempt+1}: {e}"
                    ) from e
                # Timeout or HTTP errors = correctable
                error_msg = f"scillm error on attempt {attempt+1}: {e}"
                logger.warning(error_msg)
                prior_errors.append(error_msg)
                continue

            # --- Parse and validate the output ---
            # Strip markdown fences if model wrapped output
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]
            raw = raw.strip()

            # JSON parse
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as e:
                error_msg = f"JSON parse error on attempt {attempt+1}: {e}. Raw output starts with: {raw[:100]}"
                logger.warning(error_msg)
                prior_errors.append(error_msg)
                # Add the bad output as assistant message so model sees what it produced
                messages.append({"role": "assistant", "content": raw})
                continue

            # Schema validation
            try:
                jsonschema.validate(data, UNIFIED_DOC_SCHEMA)
            except jsonschema.ValidationError as e:
                error_msg = f"Schema validation failed on attempt {attempt+1}: {e.message}"
                logger.warning(error_msg)
                prior_errors.append(error_msg)
                messages.append({"role": "assistant", "content": raw})
                continue

            # Success
            if attempt > 0:
                logger.info(f"Schematron self-corrected on attempt {attempt+1} after {len(prior_errors)} error(s)")
            return data

        # All attempts exhausted — raise with full error history
        error_history = "; ".join(f"[{i+1}] {e}" for i, e in enumerate(prior_errors))
        raise RuntimeError(
            f"Schematron failed after {self.schematron_config.max_attempts} attempts. "
            f"Error history: {error_history}"
        )

    def _manifest_document(self, data: Dict[str, Any]) -> UnifiedDocument:
        """Converts the LLM JSON output to strong UnifiedDocument types."""
        blocks: List[BaseBlock] = []
        
        # We need a predictable way to map blocks to sections. 
        # The LLM returns a flat list of blocks. We must infer hierarchy from headings.
        
        # 1. Create Blocks
        for i, b in enumerate(data.get("blocks", [])):
            b_type = b.get("type")
            content = b.get("content")
            
            # Common metadata
            meta = BlockMetadata(
                confidence=1.0, 
                page_number=1, # HTML is single page
                attributes=b.get("metadata", {})
            )
            
            # Map to blocks
            if b_type == "heading":
                blocks.append(BaseBlock(
                    id=f"blk-{i}", 
                    type=BlockType.HEADING, 
                    content=str(content), 
                    metadata=meta
                ))
            elif b_type == "table":
                # Try to parse table content if it's a dict (rows/cols)
                # If LLM returned a string, wrap it.
                if isinstance(content, dict):
                    # Expecting: {headers: [], rows: []}
                    headers = content.get("headers", [])
                    rows_data = content.get("rows", [])
                    
                    # Convert to TableCells
                    cells = []
                    # Add headers
                    for c_idx, h_txt in enumerate(headers):
                        cells.append(TableCell(
                            row=0, col=c_idx, content=str(h_txt), style={"is_header": True}
                        ))
                    # Add rows
                    for r_idx, row in enumerate(rows_data):
                        # row might be list or dict
                        row_list = row if isinstance(row, list) else list(row.values())
                        for c_idx, cell_txt in enumerate(row_list):
                            cells.append(TableCell(
                                row=r_idx+1, col=c_idx, content=str(cell_txt)
                            ))
                            
                    blocks.append(TableBlock(
                        id=f"blk-{i}",
                        type=BlockType.TABLE,
                        content=str(content.get("title", "Table")), # Content is title/caption
                        rows=len(rows_data) + 1,
                        cols=len(headers) if headers else 0,
                        cells=cells,
                        headers=[0],
                        metadata=meta
                    ))
                else:
                    # Fallback string table
                    blocks.append(BaseBlock(
                        id=f"blk-{i}",
                        type=BlockType.TABLE,
                        content=str(content),
                        metadata=meta
                    ))
            elif b_type == "image":
                 blocks.append(ImageBlock(
                    id=f"blk-{i}",
                    type=BlockType.IMAGE,
                    src=str(content), # Content is src? Or description?
                    # If content is object: {src: ..., alt: ...}
                    # Schematron prompt might need tuning to output object here.
                    # For now assume content is description/alt and we misuse src?
                    # Let's assume content is the description.
                    content=str(content),
                    metadata=meta
                ))
            else:
                # Default paragraph
                blocks.append(BaseBlock(
                    id=f"blk-{i}",
                    type=BlockType.PARAGRAPH,
                    content=str(content),
                    metadata=meta
                ))

        # 2. Build Hierarchy
        hierarchy = self._build_hierarchy(blocks)
        
        # 3. Assign Parent IDs
        self._assign_parent_ids(hierarchy, blocks)

        return UnifiedDocument(
            id=data.get("title", "untitled"),
            source_type=SourceType.HTML,
            source_path=str(self.file_path),
            blocks=blocks,
            metadata=DocumentMetadata(title=data.get("title")),
            hierarchy=hierarchy
        )

    def _build_hierarchy(self, blocks: List[BaseBlock]) -> HierarchyNode:
        """
        Reconstructs the section hierarchy from HEADING blocks.
        Mirrors s04_section_builder logic:
        - Stack-based parent resolution
        - Root node (level 0)
        - Handling of skipped levels (H1 -> H3 becomes child of H1)
        """
        root = HierarchyNode(
            id="root",
            title="Root",
            level=0, 
            block_id="root", 
            children=[],
            breadcrumb=[]
        )
        
        # Stack of active sections, starting with root
        stack: List[HierarchyNode] = [root]
        
        for block in blocks:
            if block.type == BlockType.HEADING:
                # 1. Determine level (default to 1 if missing)
                try:
                    level = int(block.metadata.attributes.get("level", 1))
                except (ValueError, TypeError):
                    level = 1
                
                # 2. Find parent by popping stack until we find a node with level < current_level
                #    (e.g. if we are H2, we pop H3, H2s until we find H1 or Root)
                while stack[-1].level >= level and stack[-1].id != "root":
                    stack.pop()
                    
                parent = stack[-1]
                
                # 3. Create new node
                node = HierarchyNode(
                    id=f"sec-{block.id}",
                    title=str(block.content),
                    level=level,
                    block_id=block.id,
                    children=[],
                    parent_id=parent.id,
                    breadcrumb=parent.breadcrumb + [str(block.content)]
                )
                
                # 4. Link to parent
                parent.children.append(node)
                
                # 5. Push to stack as current active section
                stack.append(node)
                
        return root

    def _assign_parent_ids(self, hierarchy: HierarchyNode, blocks: List[BaseBlock]) -> None:
        """
        Assigns parent_id to all content blocks based on the hierarchy.
        Walks the block list linearly and tracks the current active section.
        """
        # Map block_id -> section_id for all HEADING blocks
        heading_to_section = {}
        
        def map_headings(node: HierarchyNode):
            if node.block_id and node.block_id != "root":
                heading_to_section[node.block_id] = node.id
            for child in node.children:
                map_headings(child)
        
        map_headings(hierarchy)
        
        # Default to root
        current_section_id = "root"
        
        for block in blocks:
            if block.type == BlockType.HEADING:
                # This block initiates a new section.
                # The heading block ITSELF belongs to the PARENT section in the document flow,
                # but functionally it represents the start of the new section.
                # In UnifiedDocument, heading block usually has parent_id = parent_section_id.
                # The content *following* it has parent_id = this_section_id.
                
                sec_id = heading_to_section.get(block.id)
                if sec_id:
                    # Find the node to get its parent_id
                    # (We can't easily look up node by ID here without a map, 
                    #  but we know the logic: headers belong to their parent level)
                    # Let's set the heading's parent to the *current* context before the switch?
                    # actually, the hierarchy defines the parent.
                    # We should probably look up the node in the hierarchy.
                    pass
                
                # Update current section for SUBSEQUENT blocks
                if sec_id:
                    current_section_id = sec_id
                    
                # The heading block itself needs a parent_id. 
                # Ideally it should be the parent of the section it defines.
                # But for simplicity in this linear pass, let's assign it to the *enclosing* section 
                # (which is effectively what current_section_id was BEFORE update, 
                #  IF it is a child. But if it's a sibling, it shares the same parent).
                # 
                # Let's use the hierarchy to correctly set the heading's parent_id.
                # We can do this by finding the node and getting its parent_id.
                # Since we don't have a quick node lookup, let's do a second pass or build a map.
                pass 
                
            else:
                # Content block belongs to current section
                block.parent_id = current_section_id
        
        # Fix heading parent_ids using the hierarchy map
        # (We need to map section_id -> parent_section_id)
        section_parent_map = {}
        def build_parent_map(node: HierarchyNode):
            if node.parent_id:
                section_parent_map[node.id] = node.parent_id
            for child in node.children:
                build_parent_map(child)
        build_parent_map(hierarchy)
        
        for block in blocks:
            if block.type == BlockType.HEADING:
                sec_id = heading_to_section.get(block.id)
                if sec_id:
                    # The heading "belongs" to the section above it
                    block.parent_id = section_parent_map.get(sec_id, "root")
