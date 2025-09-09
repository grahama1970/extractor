#!/usr/bin/env python3
"""
Pipeline Stage: LLM-Based Section Reflow (offline)

This script is the final text processing stage. It runs offline (no DB access)
to perform a powerful hybrid search for relevant annotations. This rich,
dynamically-fetched context is then used to guide a VLM in reflowing and
improving the section's content. All database and search logic is self-contained.
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, cast
from datetime import datetime
import base64
import numpy as np
from textwrap import dedent
import pandas as pd
from typing import Optional

# Direct, non-abstracted, top-level imports for core functionality
try:
    try:
        import typer
        _HAS_TYPER = True
    except Exception:
        _HAS_TYPER = False
        class _TyperShim:
            def __init__(self,*a,**k): pass
            def command(self,*a,**k): return lambda f: f
            def __call__(self,*a,**k): print("Typer not installed; CLI disabled")
        def _opt(*a,**k): return None
        def _arg(*a,**k): return None
        typer = _TyperShim()  # type: ignore
        typer.Typer = _TyperShim  # type: ignore
        typer.Option = _opt  # type: ignore
        typer.Argument = _arg  # type: ignore
        typer.secho = print  # type: ignore

    _HAS_TYPER = True
except Exception:
    _HAS_TYPER = False
    class _TyperShim:
        def __init__(self,*a,**k): pass
        def command(self,*a,**k): return lambda f: f
        def __call__(self,*a,**k): print("Typer not installed; CLI disabled")
    def _opt(*a,**k): return None
    def _arg(*a,**k): return None
    typer = _TyperShim()  # type: ignore
    typer.Typer = _TyperShim  # type: ignore
    typer.Option = _opt  # type: ignore
    typer.Argument = _arg  # type: ignore
    typer.secho = print  # type: ignore

from dotenv import load_dotenv, find_dotenv
from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache
from loguru import logger
from rich.console import Console
import litellm
from tqdm.asyncio import tqdm_asyncio
 
from extractor.core.services.utils.json_utils import clean_json_string
from extractor.pipeline.utils.image_io import (
    get_section_image_b64,
    get_table_image_b64,
    get_figure_image_b64,
    get_annotation_image_b64,
)
from extractor.pipeline.utils.diagnostics import start_resource_sampler, stop_resource_sampler, get_run_id, iso_now, make_event, snapshot_resources, build_stage_timings, classify_llm_error, gpu_metrics_available
from extractor.pipeline.utils.litellm_call import litellm_call
from extractor.pipeline.utils.model_params import build_chat_messages, build_chat_extras, image_file_to_data_url
from extractor.pipeline.utils.vision import preflight_vision_support
from extractor.pipeline.utils.ann_index import build_ann_index, query_ann_index, load_ann_index

# --- Initialization & Configuration ---

if not load_dotenv(find_dotenv(), override=False):
    logger.warning(".env not found; proceeding with process environment only.")

# Initialize LiteLLM cache to prevent duplicate calls
try:
    initialize_litellm_cache()
except Exception as _e:
    logger.warning(f"LiteLLM cache init failed (continuing): {_e}")

logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{function}:{line}</cyan> - <level>{message}</level>")

app = typer.Typer(help="Reflows document sections using a VLM (offline)")
STAGE07_DEBUG = os.getenv("STAGE07_DEBUG", "").lower() in ("1", "true", "yes", "y")
console = Console()

# Hybrid search removed; Stage 07 runs fully offline

# Text embedding model (lazy-loaded)
text_embedding_model: Any = None
from extractor.pipeline.utils.embeddings import ensure_embedder as _ensure_embedder
# removed local embedder implementation

# Configuration from environment variables
# Use Ollama for free testing, or set LITELLM_VLM_MODEL env var for other providers
# Use GPT-5 for reflow by default; can override via env
# Default to Gemini Flash for multimodal reflow; override via LITELLM_VLM_MODEL
LLM_MODEL = os.getenv("LITELLM_VLM_MODEL", "gemini/gemini-2.5-flash")
MAX_CONCURRENT_CALLS = int(os.getenv("MAX_CONCURRENT_LLM_CALLS", 3))
LLM_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_CALLS)
SEMANTIC_TOP_K = int(os.getenv("SEMANTIC_ANNOTATION_TOP_K", 5))
TABLE_CONF_THRESHOLD = float(os.getenv("STAGE07_TABLE_CONFIDENCE_THRESHOLD", "0.6"))
INCLUDE_FIGURE_IMAGES = os.getenv("STAGE07_INCLUDE_FIGURES", "false").lower() in ("1", "true", "yes", "y")
MAX_ANNOTATION_IMAGES = int(os.getenv("STAGE07_MAX_ANNOTATION_IMAGES", "2"))
ATTACH_SECTION_IMAGE = os.getenv("STAGE07_ATTACH_SECTION_IMAGE", "true").lower() in ("1", "true", "yes", "y")
SCHEMA_MODE = os.getenv("STAGE07_SCHEMA_MODE", "reflow_json").strip().lower()  # "text" | "reflow_json"


# --- Core LLM and Prompting Functions ---

def build_reflow_prompt(section_data: Dict[str, Any]) -> str:
    """Builds a simplified prompt focused on the core reflow task."""
    
    table_count = len(section_data.get('tables', []))
    figure_count = len(section_data.get('figures', []))
    
    return dedent(f"""
        Clean up and reflow this PDF section into proper Markdown.

        Section: "{section_data.get('title', 'Untitled')}"
        Tables: {table_count}
        Figures: {figure_count}

        Raw text to clean up:
        ---
        {section_data.get('raw_text', '')}
        ---

        Fix common PDF extraction issues like words split across lines, OCR errors, and broken table formatting.

        Return ONLY a JSON object with the following keys:
        {{
            "reflowed_text": "The cleaned Markdown text.",
            "ocr_corrections": {{'erroneous text': 'corrected text'}},
            "improvements_made": "A brief summary of what was fixed."
        }}
    """).strip()
def get_section_image_b64(section_data: Dict[str, Any], base_dir: Path) -> Optional[str]:
    """Loads a pre-extracted image and encodes it to base64 with path normalization."""
    image_path_str = section_data.get("visual_path") or section_data.get("image_path")
    if not image_path_str:
        return None
    return _safe_read_image_b64(image_path_str, base_dir)


def _safe_read_image_b64(path_str: str, base_dir: Path) -> Optional[str]:
    """Resolve relative/duplicated paths and return base64 data for an image path."""
    try:
        def _candidates() -> List[Path]:
            raw = Path(path_str)
            c: List[Path] = []
            c.append(raw)
            if not raw.is_absolute():
                c.append(base_dir / raw)
            # Build from combined parts, then trim duplicates
            parts = (base_dir / raw).parts if not raw.is_absolute() else raw.parts
            if parts.count("src") > 1:
                src_idx = parts.index("src")
                trimmed = Path(*parts[src_idx:])
                c.append(trimmed)
                c.append(Path.cwd() / trimmed)
            if "results" in parts:
                idxs = [i for i, p in enumerate(parts) if p == "results"]
                if idxs:
                    last_idx = idxs[-1]
                    rel_after = Path(*parts[last_idx+1:])
                    if str(rel_after):
                        c.append(base_dir / rel_after)
            # Deduplicate while preserving order
            out: List[Path] = []
            seen = set()
            for x in c:
                key = str(x)
                if key not in seen:
                    seen.add(key)
                    out.append(x)
            return out

        for cand in _candidates():
            if cand.exists():
                with open(cand, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
        logger.warning(f"Image not found after normalization attempts: {path_str}")
        return None
    except Exception as e:
        logger.error(f"Failed to load image {path_str}: {e}")
        return None

def get_table_image_b64(table: Dict[str, Any], base_dir: Path) -> Optional[str]:
    """Return base64 image for a table if available."""
    path = table.get("table_image_path") or table.get("image_path")
    if not path:
        return None
    return _safe_read_image_b64(path, base_dir)

def get_figure_image_b64(figure: Dict[str, Any], base_dir: Path) -> Optional[str]:
    """Return base64 image for a figure if available."""
    path = figure.get("image_path")
    if not path:
        return None
    return _safe_read_image_b64(path, base_dir)

def get_annotation_image_b64(annot: Dict[str, Any], base_dir: Path) -> Optional[str]:
    """Return base64 image for an annotation if available."""
    path = annot.get("image_path")
    if not path:
        return None
    return _safe_read_image_b64(path, base_dir)

def _sanitize_text(s: Optional[str]) -> str:
    if not s:
        return ""
    removals = [
        "\u200e", "\u200f",  # LRM/RLM
        "\u200b", "\u200c", "\u200d",  # zero-width
        "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",  # bidi overrides
        "\u2066", "\u2067", "\u2068", "\u2069",  # isolates
    ]
    s2 = str(s)
    for ch in removals:
        s2 = s2.replace(ch, "")
    s2 = s2.replace("\u00a0", " ")
    return "\n".join(" ".join(line.split()) for line in s2.splitlines()).strip()

def build_section_context_text(section: Dict[str, Any]) -> str:
    """Compose concise textual context including tables, figures, and the most relevant annotations (with text)."""
    lines: List[str] = []
    title = _sanitize_text(section.get("title", "Untitled"))
    level = section.get("level", 0)
    page_start = section.get("page_start")
    page_end = section.get("page_end")
    lines.append(f"Section: {title} (level {level}) pages {page_start}–{page_end}")
    # Include a concise JSON-like section summary to ground the LLM
    sec_num = section.get('metadata', {}).get('section_number') or section.get('section_number')
    sec_hash = section.get('metadata', {}).get('section_hash') or section.get('section_hash')
    lines.append("Section JSON Summary:")
    lines.append(json.dumps({
        'id': section.get('id'),
        'title': title,
        'level': level,
        'section_number': sec_num,
        'section_hash': sec_hash,
        'page_start': page_start,
        'page_end': page_end,
        'blocks_count': len(section.get('blocks', [])),
    }, ensure_ascii=False))

    raw_text = _sanitize_text(section.get("source_text") or section.get("merged_text") or section.get("raw_text", ""))
    if raw_text:
        snippet = raw_text if len(raw_text) <= 6000 else raw_text[:6000] + " ..."
        lines.append("Source Text:")
        lines.append(snippet)

    # Tables summary
    tables = section.get("tables", [])
    if tables:
        lines.append(f"Tables: {len(tables)}")
        for t in tables[:3]:
            pm = t.get("pandas_metrics", {}) or {}
            cols = pm.get("columns", [])
            shape = pm.get("shape", [])
            density = pm.get("data_density")
            lines.append(f"- Table idx {t.get('table_index')}: shape={shape}, columns={cols}, density={density}")
            rows = t.get("pandas_df", [])[:3] or t.get("pandas_df_dict", [])[:3]
            if rows:
                try:
                    lines.append(f"  sample_rows: {json.dumps(rows, ensure_ascii=False)[:500]}")
                except Exception:
                    pass
        # Optional: enforce exact column hints via env for deterministic reflow
        try:
            import os as _os
            forced = _os.getenv('STAGE07_FORCE_TABLE_COLUMNS', '').strip()
            if forced:
                # comma-separated list
                cols_hint = [c.strip() for c in forced.split(',') if c.strip()]
                if cols_hint:
                    lines.append("Table Hints:")
                    lines.append(f"columns_exact: {json.dumps(cols_hint, ensure_ascii=False)}")
        except Exception:
            pass

    # Figures summary
    figures = section.get("figures", [])
    if figures:
        lines.append(f"Figures: {len(figures)}")
        for f in figures[:3]:
            desc = f.get("ai_description", "")
            lines.append(f"- Figure {f.get('figure_id')}: {desc[:300]}")

    # Annotations on the same pages (include by default) with interpretation if available
    def _blocks_to_text(blocks: List[Dict[str, Any]], max_chars: int = 400) -> str:
        parts: List[str] = []
        for blk in blocks or []:
            for ln in blk.get("lines", []):
                for sp in ln.get("spans", []):
                    t = _sanitize_text(sp.get("text") or "")
                    if t:
                        parts.append(t)
        s = " ".join(parts)
        s = " ".join(s.split())
        return s if len(s) <= max_chars else s[:max_chars] + " ..."

    annots = section.get("annotations", [])
    if annots:
        lines.append(f"On-page Annotations: {len(annots)}")
        for a in annots:
            a_type = a.get("type")
            sim = a.get("similarity")
            interp = a.get("interpretation") or {}
            inside = _blocks_to_text(a.get("inside_blocks", []), 300)
            above = _blocks_to_text(a.get("above_blocks", []), 200)
            below = _blocks_to_text(a.get("below_blocks", []), 200)
            lines.append(json.dumps({
                'id': a.get('id'),
                'type': a_type,
                'similarity': sim,
                'interpretation': {
                    'title': interp.get('title'),
                    'summary': interp.get('summary'),
                    'entities': interp.get('entities'),
                    'labels': interp.get('labels'),
                },
                'inside': inside,
                'above': above,
                'below': below,
            }, ensure_ascii=False))

    return "\n".join(lines)





async def reflow_section_with_llm(section_data: Dict[str, Any], results_base_dir: Path, *, include_images: bool, allow_fallback: bool) -> Dict[str, Any]:
    """Reflow a section using multimodal context (section/table/figure/annotation) and return structured JSON."""
    try:
        sec_diags = []
        # Decide if the model supports multimodal inputs
        supports_vision = any(
            kw in (LLM_MODEL or "").lower()
            for kw in ("gpt-5", "gpt-4o", "gpt-4.1", "gpt-4-vision", "claude-3", "gemini", "llava", "qwen-vl", "grok-vision")
        )

        # Build textual context
        context_text = build_section_context_text(section_data)
        # Enforce vision requirement before constructing images

        # Build user content (text + images if supported)
        user_content: Any
        image_blocks: List[Dict[str, Any]] = []
        # Optionally perform a lightweight preflight to avoid large failed calls
        if include_images:
            try:
                ok = await preflight_vision_support(LLM_MODEL, timeout_sec=10)
                if ok:
                    supports_vision = True
                else:
                    supports_vision = False
            except Exception:
                pass
        if supports_vision and include_images:
            # Section visual
            sec_b64 = get_section_image_b64(section_data, results_base_dir)
            if sec_b64:
                image_blocks.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{sec_b64}"}})
                try:
                    sec_diags.append(make_event("07_reflow_section","info","section_image_attached","Included section image", {}))
                except Exception:
                    pass
            # Table images: include only low-confidence tables
            def _tconf(t):
                try:
                    pm = t.get("pandas_metrics") or {}
                    shape = pm.get("shape") or [0, 0]
                    rows = int(shape[0] or 0)
                    density = float(pm.get("data_density") or 0.0)
                    camel = t.get("camelot_metrics") or {}
                    acc = float(camel.get("accuracy") or 0.0)
                    white = float(camel.get("whitespace") or 0.0)
                    score = 0.0
                    score += 0.2 if rows >= 3 else 0.0
                    score += min(max(density, 0.0), 1.0) * 0.4
                    score += min(max(acc / 100.0, 0.0), 1.0) * 0.4
                    score -= min(max(white / 100.0, 0.0), 1.0) * 0.1
                    return max(0.0, min(1.0, score))
                except Exception:
                    return 0.0
            for t in section_data.get("tables", []) or []:
                conf = _tconf(t)
                if conf < TABLE_CONF_THRESHOLD:
                    tb64 = get_table_image_b64(t, results_base_dir)
                    if tb64:
                        try:
                            sec_diags.append(make_event("07_reflow_section","info","table_image_attached","Included table image (low confidence)", {"table_index": t.get("table_index"), "confidence": conf }))
                        except Exception:
                            pass
                        image_blocks.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{tb64}"}})
            # Figure images (optional via env)
            if INCLUDE_FIGURE_IMAGES:
                for f in section_data.get("figures", [])[:2]:
                    fb64 = get_figure_image_b64(f, results_base_dir)
                    if fb64:
                        try:
                            sec_diags.append(make_event("07_reflow_section","info","figure_image_attached","Included figure image", {"figure_id": f.get("figure_id") }))
                        except Exception:
                            pass
                        image_blocks.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{fb64}"}})
            # Annotation images: include top-K by similarity/text length
            def _ann_score(a):
                try:
                    sim = float(a.get("similarity") or 0.0)
                except Exception:
                    sim = 0.0
                inside_len = 0
                try:
                    for blk in a.get("inside_blocks", []) or []:
                        for ln in blk.get("lines", []) or []:
                            for sp in ln.get("spans", []) or []:
                                inside_len += len((sp.get("text") or "").strip())
                except Exception:
                    pass
                return sim + 0.001 * min(inside_len, 2000)
            anns = sorted(section_data.get("annotations", []) or [], key=_ann_score, reverse=True)[:MAX_ANNOTATION_IMAGES]
            for a in anns:
                ab64 = get_annotation_image_b64(a, results_base_dir)
                if ab64:
                    image_blocks.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{ab64}"}})

            
            # Attachments summary (counts are approximate by source lists)
            try:
                att_counts = {
                    'tables': len(section_data.get('tables', [])[:2]),
                    'figures': len(section_data.get('figures', [])[:2]),
                    'annotations': len(section_data.get('annotations', [])[:2]),
                }
                sec_diags.append(make_event('07_reflow_section','info','attachments_summary', 'Attached images for reflow', att_counts))
            except Exception:
                pass
            user_content = [{"type": "text", "text": context_text}] + image_blocks
        elif supports_vision and not include_images:
            user_content = [{"type": "text", "text": context_text}]
        else:
            user_content = f"""{context_text}

[Note: Images omitted because the selected model does not support vision]"""

        if SCHEMA_MODE == "reflow_json":
            system_prompt = dedent("""
            You are a technical reflow engine. Given a PDF-extracted section JSON, compact tables, and a few images, output a single reflowed section JSON that merges contiguous content for LLM use and DB storage.

            Core requirements
            - Merge contiguous text into coherent paragraphs (fix hyphenation, broken words, OCR joins). Remove duplicated headers/footers and page artifacts.
            - Merge contiguous tables, including those that span pages, into one logical table positioned at the first fragment.
            - Preserve reading order: top→bottom, left→right, across pages.
            - Prefer provided tables/pandas content; use images only for context or disambiguation.

            Data Integrity (strict)
            - Tables: DO NOT change cell content. No spelling “corrections”, translations, unit changes, rounding, normalization, inference, or reformatting. Keep numeric formats as-is.
            - Allowed in tables only: remove intra-cell newlines/excess spaces (join without changing character order); flatten multi-row headers by concatenation delimiters.
            - Forbidden in tables: reordering rows/columns, filling blanks, deduping, computing totals.
            - Text/Headings/Lists: Fix OCR splits/hyphenation and obvious typos only outside tables. Record fixes in ocr_corrections.

            Return exactly this JSON (no prose, no fences):
            {
              "reflowed_json": {
                "section_id": string,
                "title": string,
                "blocks": [
                  { "type": "heading", "level": int, "text": string, "source": { "pages": [int], "block_ids": [string] } },
                  { "type": "paragraph", "text": string, "source": { "pages": [int], "block_ids": [string] } },
                  { "type": "list", "style": "bulleted|numbered", "items": [string, ...], "source": { "pages": [int], "block_ids": [string] } },
                  { "type": "table", "title": string|null, "columns": [string,...], "rows": [[string|number|null,...],...],
                    "confidence": { "status": "high|medium|low", "density": number|null, "source": "camelot+pandas" },
                    "markdown": string|null, "markdown_provenance": "image"|null,
                    "image_refs": [string,...], "source": { "table_indices": [int], "page_indices": [int] } },
                  { "type": "figure", "title": string|null, "caption": string|null, "alt": string, "image_ref": string, "source": { "pages": [int], "block_ids": [string] } }
                ]
              },
              "ocr_corrections": { "erroneous": "corrected", ... },
              "improvements_made": string,
              "summary": string
            }

            Notes
            - Tables: build from provided columns+rows; ensure exact cell content; trim whitespace only. Include markdown only if pandas failed or confidence is low, in which case set markdown_provenance="image" and attach image_refs.
            - Figures: include concise caption and set image_ref to uploaded filename.
            - Source traceability: populate source.pages/block_ids when available; omit if unknown.
            """).strip()
        else:
            system_prompt = dedent("""
            You are a technical editor. Given raw PDF-extracted section text plus structured context (tables with pandas metrics, figure descriptions, and nearby annotations), produce a clean Markdown reflow of the section.
            - Fix broken words, hyphenation across lines, and common OCR errors.
            - Keep semantics but remove duplicated headers/footers.
            - Data Integrity (strict for tables): DO NOT change cell content; if tables are present, include Markdown tables only when the table extraction is reliable (high density/consistent columns). Otherwise, summarize and reference the image. Record non-table OCR fixes in ocr_corrections.

            Output strictly JSON with keys:
              - "reflowed_text": "string (Markdown)"
              - "ocr_corrections": {"erroneous": "corrected", ...}
              - "improvements_made": "short description of the fixes"
              - "summary": "1–3 sentences summarizing the section content"
            Do not include explanations outside JSON.
            """).strip()

        # Limit context size for GPT-5 stability
        if "gpt-5" in (LLM_MODEL or "").lower():
            context_text = context_text[:3000]
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        # Attach images for Chat Completions (data URL parts)
        if include_images:
            max_images = int(os.getenv("STAGE07_MAX_IMAGES", "6"))
            attached = 0
            def _attach_blocks(b64: Optional[str], kind: str, meta: dict):
                nonlocal attached, image_blocks
                if b64 and attached < max_images:
                    image_blocks.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
                    try:
                        sec_diags.append(make_event("07_reflow_section","info",f"{kind}_image_attached","Included image", meta))
                    except Exception:
                        pass
                    attached += 1
            if sec_b64:
                _attach_blocks(sec_b64, "section", {"section_id": section_data.get("id")})
            for t in section_data.get("tables", []) or []:
                conf = _tconf(t)
                if conf < TABLE_CONF_THRESHOLD:
                    _attach_blocks(get_table_image_b64(t, results_base_dir), "table", {"table_index": t.get("table_index"), "confidence": conf})
            if INCLUDE_FIGURE_IMAGES:
                for f in section_data.get("figures", [])[:2]:
                    _attach_blocks(get_figure_image_b64(f, results_base_dir), "figure", {"figure_id": f.get("figure_id")})
            for a in anns:
                _attach_blocks(get_annotation_image_b64(a, results_base_dir), "annotation", {"annotation_id": a.get("id")})

        # LLM call: prefer OpenAI Responses API for GPT-5 with reasoning
        # Single path: Chat Completions via litellm_call
        sid = os.getenv("LITELLM_SESSION_ID") or get_run_id()
        # Instrumentation: write request summary
        try:
            logs_dir = results_base_dir / "07_reflow_section" / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            def _image_bytes(data_url: str) -> int:
                try:
                    if not isinstance(data_url, str) or "," not in data_url:
                        return 0
                    b64 = data_url.split(",", 1)[1]
                    # Approximate decoded length
                    return int(len(b64) * 3 / 4)
                except Exception:
                    return 0
            req_info = {
                "model": LLM_MODEL,
                "context_length": len(context_text),
                "images_count": sum(1 for c in responses_user_content if c.get("type") == "input_image"),
                "image_bytes": [
                    _image_bytes(c.get("image_url", "")) for c in responses_user_content if c.get("type") == "input_image"
                ],
                "session_id": sid,
            }
            (logs_dir / f"request_info_{section_data.get('id','section')}.json").write_text(json.dumps(req_info, indent=2))
        except Exception:
            pass
        # Attempt 1: Chat Completions with standardized messages (system + user text + image_url data URL)
        try:
            # Build image data URL for section image if present and attach to messages
            image_data_url = None
            try:
                # prefer section image
                if sec_b64:
                    image_data_url = f"data:image/png;base64,{sec_b64}"
            except Exception:
                image_data_url = None
            system_text = (
                "You are a strict JSON reflow engine. Return ONLY a JSON object with keys: "
                "reflowed_json, ocr_corrections, improvements_made, summary. No code fences. "
                "Requirements: reflowed_json.blocks must preserve reading order and include: "
                "(a) a single merged table block when tables are fragmented/continued. The table title MUST start with 'INFERRED:' (e.g., INFERRED: …). Use the nearby text to form a concise title but always prefix with INFERRED:. The table must include 'columns' and 'rows' consistent with provided context. When column hints are provided in context, use those exact column names verbatim and in order; do NOT rename or substitute synonyms. Do not alter cell values; "
                "(b) a figure block with a non-empty title (literal or INFERRED), short caption, and image_ref when applicable. "
                "Always provide ocr_corrections and improvements_made; include summary."
            )
            messages = build_chat_messages(system_text, context_text, image_data_url)
            extras = build_chat_extras(LLM_MODEL)
            call_params = {"model": LLM_MODEL, "messages": messages, **extras, "timeout": 60}
            results = await litellm_call([call_params], wrap_json=False, concurrency=1, desc="Reflow Section", session_id=sid)
            resp = results[0] if results else ""
            try:
                (logs_dir / f"response_strict_{section_data.get('id','section')}.json").write_text(
                    json.dumps(resp, default=str, indent=2) if isinstance(resp, dict) else str(resp)
                )
            except Exception:
                pass
        except Exception as e:
            resp = ""

        # Normalize response to get content
        content: Optional[str] = None
        if isinstance(resp, str):
            content = resp
        if isinstance(resp, dict):
            try:
                # OpenAI Responses API shape
                if "output" in resp:
                    out = resp.get("output") or []
                    if out and isinstance(out, list):
                        content_items = out[0].get("content") or []
                        if content_items and isinstance(content_items, list):
                            text_item = next((c for c in content_items if c.get("type") == "output_text" or c.get("type") == "text"), None)
                            if text_item:
                                content = text_item.get("text") or text_item.get("content")
                # Chat Completions shape
                if not content:
                    choices = resp.get("choices") or []
                    if choices:
                        msg = choices[0].get("message") or {}
                        content = msg.get("content")
            except Exception:
                content = None
        else:
            if include_images and not supports_vision:
                try:
                    sec_diags.append(make_event("07_reflow_section","info","vision_not_supported","Model lacks vision; images not sent", {}))
                except Exception:
                    pass
            ch = getattr(resp, "choices", None)
            if ch:
                try:
                    ch0 = ch[0]
                    msg = getattr(ch0, "message", None)
                    if msg is not None and getattr(msg, "content", None) is not None:
                        content = msg.content  # type: ignore[attr-defined]
                    else:
                        txt = getattr(ch0, "text", None)
                        if isinstance(txt, str):
                            content = txt
                except Exception:
                    content = None

        if not isinstance(content, str) or not content.strip():
            # Attempt 2: Relaxed mode (no response_format). Parse free-form via clean_json_string downstream.
            try:
                # Relaxed: same messages, no response_format extras
                call_params = {"model": LLM_MODEL, "messages": messages, "timeout": 60}
                results = await litellm_call([call_params], wrap_json=False, concurrency=1, desc="Reflow Section (relaxed)", session_id=sid)
                resp2 = results[0] if results else ""
                try:
                    (logs_dir / f"response_relaxed_{section_data.get('id','section')}.json").write_text(
                        json.dumps(resp2, default=str, indent=2) if isinstance(resp2, dict) else str(resp2)
                    )
                except Exception:
                    pass
            except Exception:
                resp2 = ""
            content = resp2 if isinstance(resp2, str) else None
        if not isinstance(content, str) or not content.strip():
            typer.secho("Stage 07: LLM returned empty content.", fg=typer.colors.RED)
            raise RuntimeError("Stage 07: LLM returned empty content. Verify API keys and Chat Completions access; inspect logs in 07_reflow_section/logs for request_info and response dumps.")

        # Parse/repair JSON robustly
        try:
            parsed = clean_json_string(content, return_dict=True)
            if isinstance(parsed, dict):
                result = parsed
            elif isinstance(parsed, list):
                # If the model returned a top-level list, try using the first object
                result = parsed[0] if parsed and isinstance(parsed[0], dict) else {"reflowed_text": content}
            elif isinstance(parsed, str):
                tmp = json.loads(parsed)
                result = tmp if isinstance(tmp, dict) else {"reflowed_text": content}
            else:
                result = {"reflowed_text": content}
        except Exception:
            logger.warning("Invalid JSON from LLM; failing per policy (no fallback)")
            try:
                sec_diags.append(make_event("07_reflow_section","warning","llm_invalid_json","LLM returned invalid JSON", {}))
            except Exception:
                pass
            raise ValueError("Stage 07: LLM returned invalid JSON. See logs in 07_reflow_section/logs and verify the model returns strict JSON (no code fences) matching schema mode expectations.")

        # Enforce schema presence; do not accept wrappers or missing keys
        if SCHEMA_MODE == "reflow_json":
            if not (isinstance(result, dict) and result.get("reflowed_json")):
                raise ValueError("Stage 07: Expected 'reflowed_json' in model output for schema mode but it was missing. Ensure the prompt instructs returning the exact schema.")
            out = {**section_data}
            out.update({
                "reflowed_json": result.get("reflowed_json"),
                "ocr_corrections": result.get("ocr_corrections", {}),
                "improvements_made": result.get("improvements_made", ""),
                "summary": result.get("summary", ""),
                "reflow_status": "success",
            })
        else:
            if not (isinstance(result, dict) and result.get("reflowed_text")):
                raise ValueError("Stage 07: Expected 'reflowed_text' in model output but it was missing. Ensure the prompt instructs returning the exact keys.")
            out = {**section_data}
            out.update({
                "reflowed_text": result.get("reflowed_text"),
                "ocr_corrections": result.get("ocr_corrections", {}),
                "improvements_made": result.get("improvements_made", ""),
                "reflow_status": "success",
            })
        if STAGE07_DEBUG:
            out["quick_summary"] = result.get("summary", (section_data.get("merged_text") or section_data.get("raw_text", ""))[:280])
        try:
            md = out.setdefault("metadata", {})
            md.setdefault("diagnostics", []).extend(sec_diags)
        except Exception:
            pass
        return out
    except Exception as e:
        # Always fail (no fallback)
        try:
            info = classify_llm_error(e)
            sec_diags.append(make_event("07_reflow_section","error", info.get("code","llm_error"), info.get("message", str(e)), {}))
        except Exception:
            pass
        typer.secho(f"Stage 07: LLM call failed: {e}", fg=typer.colors.RED)
        raise RuntimeError("Stage 07 failed: LLM call did not return usable JSON. Check 07_reflow_section/logs, verify API keys, and confirm the configured Chat model is reachable.")

def consolidate_data(
    sections_path: Path,
    tables_path: Path,
    figures_path: Path,
    annotations_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Reads and merges data from previous stages (sections, tables, figures, annotations)."""
    with open(sections_path) as f:
        sections_data = json.load(f).get("sections", [])

    with open(tables_path) as f:
        tables_list = json.load(f).get("tables", [])

    with open(figures_path) as f:
        figures_list = json.load(f).get("figures", [])

    # Index by section id for quick join
    tables_by_section: Dict[str, List[Dict[str, Any]]] = {}
    for t in tables_list:
        sid = t.get("section_id")
        if sid is None:
            continue
        tables_by_section.setdefault(sid, []).append(t)

    figures_by_section: Dict[str, List[Dict[str, Any]]] = {}
    for g in figures_list:
        sid = g.get("section_id")
        if sid is None:
            continue
        figures_by_section.setdefault(sid, []).append(g)

    # Load annotations by page (optional)
    annotations_by_page: Dict[int, List[Dict[str, Any]]] = {}
    source_pdf: Optional[str] = None
    if annotations_path and annotations_path.exists():
        try:
            with open(annotations_path) as f:
                annot_payload = json.load(f)
            source_pdf = annot_payload.get("source_pdf")
            for a in annot_payload.get("annotations", []):
                p = int(a.get("page", -1))
                if p >= 0:
                    annotations_by_page.setdefault(p, []).append(a)
        except Exception as e:
            logger.warning(f"Failed to load annotations from {annotations_path}: {e}")

    def _merge_text_blocks(blocks: List[Dict[str, Any]]) -> str:
        """Minimal normalization for fallback: join non-empty lines into paragraphs.
        LLM handles full reflow; this is only for pass-through when needed.
        """
        parts: List[str] = []
        for b in blocks or []:
            txt = (b.get('text') or '').strip()
            if not txt:
                continue
            lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
            if lines:
                parts.append(" ".join(lines))
        return "\n\n".join(parts)

    for section in sections_data:
        # Source text (raw order) and minimal merged fallback from blocks
        blocks = section.get('blocks', [])
        section['source_text'] = "\n".join([(b.get('text') or '').strip() for b in blocks if (b.get('text') or '').strip()])
        section['merged_text'] = _merge_text_blocks(blocks)
        sid = section.get("id")
        if source_pdf:
            section['source_pdf'] = source_pdf

        # Attach tables and figures
        section['tables'] = tables_by_section.get(sid, [])
        section['figures'] = figures_by_section.get(sid, [])

        # Merge tables within the section when they represent header/body or continued parts across pages
        def _rows_cols(t: Dict[str, Any]) -> tuple[int, int]:
            m = t.get('pandas_metrics') or {}
            shape = m.get('shape') or [0, 0]
            try:
                return int(shape[0] or 0), int(shape[1] or 0)
            except Exception:
                return 0, 0
        def _h_iou(a: list[float], b: list[float]) -> float:
            try:
                ax0, _, ax1, _ = a
                bx0, _, bx1, _ = b
                inter = max(0.0, min(float(ax1), float(bx1)) - max(float(ax0), float(bx0)))
                uni = max(float(ax1), float(bx1)) - min(float(ax0), float(bx0))
                return float(inter/uni) if uni > 0 else 0.0
            except Exception:
                return 0.0
        def _metrics_for(df: pd.DataFrame) -> Dict[str, Any]:
            try:
                if df is None or df.empty:
                    return {"shape": [0, 0], "data_density": 0.0, "columns": []}
                total_cells = int(df.size)
                non_empty = int(df.astype(str).ne('').sum().sum())
                return {
                    "shape": [int(df.shape[0]), int(df.shape[1])],
                    "columns": [str(c) for c in df.columns],
                    "dtypes": {str(k): str(v) for k, v in df.dtypes.to_dict().items()},
                    "null_counts": {str(k): int(v) for k, v in df.isnull().sum().to_dict().items()},
                    "total_cells": total_cells,
                    "non_empty_cells": non_empty,
                    "data_density": float(non_empty / total_cells) if total_cells > 0 else 0.0,
                }
            except Exception:
                return {"shape": [0, 0], "data_density": 0.0, "columns": []}

        def _merge_section_tables(sec: Dict[str, Any]) -> None:
            tabs = list(sec.get('tables') or [])
            if len(tabs) <= 1:
                return
            # Sort by page then by table_index
            try:
                tabs.sort(key=lambda t: (int(t.get('page_index', 0) or 0), int(t.get('table_index', 0) or 0)))
            except Exception:
                pass
            merged: list[Dict[str, Any]] = tabs[:]
            i = 0
            while i < len(merged) - 1:
                t1, t2 = merged[i], merged[i+1]
                r1, c1 = _rows_cols(t1)
                r2, c2 = _rows_cols(t2)
                if c1 > 0 and c1 == c2 and (t2.get('page_index', 0) <= (t1.get('page_index', 0) or 0) + 1):
                    iou = _h_iou(t1.get('bbox', []) or [0,0,0,0], t2.get('bbox', []) or [0,0,0,0])
                    if iou >= 0.2:
                        # Case A: header (1 row) + body (>=2 rows)
                        if r1 == 1 and r2 >= 2:
                            try:
                                hdr = pd.DataFrame(t1.get('pandas_df') or [])
                                body = pd.DataFrame(t2.get('pandas_df') or [])
                                # Apply header row as column names if shape aligns
                                if len(body.columns) == len(hdr.columns):
                                    new_cols = [str(x).strip() or str(j) for j, x in enumerate(hdr.iloc[0].tolist())]
                                    body.columns = new_cols
                                t2['pandas_df'] = body.to_dict('records')
                                # Recompute metrics
                                t2['pandas_metrics'] = _metrics_for(body)
                                # Drop t1, keep t2 as merged
                                merged.pop(i)
                                continue  # stay at same index; t2 now occupies position i
                            except Exception:
                                pass
                        # Case B: both bodies with same columns -> concatenate
                        if r1 >= 2 and r2 >= 2:
                            try:
                                df1 = pd.DataFrame(t1.get('pandas_df') or [])
                                df2 = pd.DataFrame(t2.get('pandas_df') or [])
                                if len(df1.columns) == len(df2.columns):
                                    out = pd.concat([df1, df2], ignore_index=True)
                                    t1['pandas_df'] = out.to_dict('records')
                                    t1['pandas_metrics'] = _metrics_for(out)
                                    # Drop t2
                                    merged.pop(i+1)
                                    # do not advance i; re-evaluate chaining merges
                                    continue
                            except Exception:
                                pass
                i += 1
            # If multiple remain, keep the densest
            if len(merged) > 1:
                def _density(t: Dict[str, Any]) -> float:
                    m = t.get('pandas_metrics') or {}
                    try:
                        return float(m.get('data_density') or 0.0)
                    except Exception:
                        return 0.0
                keep = max(merged, key=_density)
                sec['tables'] = [keep]
            else:
                sec['tables'] = merged

        _merge_section_tables(section)

        # Attach relevant annotations by page range, then rank by semantic similarity (text-only fallback)
        page_start = int(section.get("page_start", 0) or 0)
        page_end = int(section.get("page_end", page_start) or page_start)
        candidates: List[Dict[str, Any]] = []
        for p in range(page_start, page_end + 1):
            candidates.extend(annotations_by_page.get(p, []))
        # Always include all on-page annotations by default (no cut)
        selected: List[Dict[str, Any]] = list(candidates)
        try:
            # Prefer semantic ranking when a text embedding model is available
            embedder = _ensure_embedder()
            if candidates and embedder is not None:
                # Build query text from section title + raw text
                title = section.get('title', '') or ''
                raw_text = section.get('raw_text', '') or ''
                query_text = f"{title}\n{raw_text}".strip()
                q_vec = embedder.encode(query_text, normalize_embeddings=True)

                def _blocks_to_text(blocks: List[Dict[str, Any]]) -> str:
                    lines: List[str] = []
                    for blk in blocks or []:
                        for ln in blk.get('lines', []):
                            for sp in ln.get('spans', []):
                                t = (sp.get('text') or '').strip()
                                if t:
                                    lines.append(t)
                    return ' '.join(lines)

                annot_texts: List[str] = []
                for a in candidates:
                    inside = _blocks_to_text(a.get('inside_blocks', []))
                    above = _blocks_to_text(a.get('above_blocks', []))
                    below = _blocks_to_text(a.get('below_blocks', []))
                    combined = " ".join([inside, above, below]).strip()
                    annot_texts.append(combined if combined else a.get('type', ''))

                a_vecs = embedder.encode(annot_texts, normalize_embeddings=True)
                sims = np.dot(a_vecs, q_vec)
                order = np.argsort(-sims)
                # Annotate similarity on all on-page candidates
                for i in range(len(candidates)):
                    candidates[i]["similarity"] = float(sims[i])
        except Exception as e:
            logger.warning(f"Annotation semantic ranking failed; using page-order. Reason: {e}")
            selected = candidates
        section['annotations'] = selected
        if STAGE07_DEBUG:
            try:
                section['hybrid_status'] = {
                    'page': page_start,
                    'on_page_candidates': len(candidates),
                    'selected': len(selected),
                }
            except Exception:
                pass

    return sections_data

def _structured_fallback(section_data: Dict[str, Any]) -> Dict[str, Any]:
    """Build a deterministic structured reflow (reflow_json) without LLM.

    - Merges consecutive text blocks into paragraphs
    - Converts pandas tables to table blocks (no markdown)
    - Adds figure blocks with captions from ai_description when available
    """
    def _clean_lines(text: str) -> str:
        if not text:
            return ""
        lines = [ln.strip() for ln in str(text).splitlines() if ln.strip()]
        return " ".join(lines)

    out: Dict[str, Any] = {
        "section_id": section_data.get("id") or section_data.get("section_id") or "section",
        "title": section_data.get("title") or section_data.get("display_title") or "Untitled",
        "blocks": [],
    }

    # Merge consecutive Text blocks into paragraphs
    para_text: List[str] = []
    para_pages: List[int] = []
    para_ids: List[str] = []
    for b in section_data.get("blocks", []) or []:
        btype = b.get("block_type") or b.get("type")
        if btype == "Text":
            t = _clean_lines(b.get("text") or "")
            if t:
                para_text.append(t)
                try:
                    para_pages.append(int(b.get("page", b.get("page_idx", -1))))
                except Exception:
                    pass
                if b.get("id"):
                    para_ids.append(str(b.get("id")))
            continue
        # flush paragraph when hitting a non-text block
        if para_text:
            out["blocks"].append({
                "type": "paragraph",
                "text": " ".join(para_text),
                "source": {"pages": sorted(list({p for p in para_pages if isinstance(p, int) and p >= 0})), "block_ids": para_ids},
            })
            para_text, para_pages, para_ids = [], [], []
        # carry through other block types only as markers (figures handled below)
    if para_text:
        out["blocks"].append({
            "type": "paragraph",
            "text": " ".join(para_text),
            "source": {"pages": sorted(list({p for p in para_pages if isinstance(p, int) and p >= 0})), "block_ids": para_ids},
        })

    # Tables → table blocks using pandas data
    for t in section_data.get("tables", []) or []:
        pm = t.get("pandas_metrics") or {}
        cols = list(pm.get("columns") or [])
        rows_raw = t.get("pandas_df") or []
        rows = []
        if rows_raw and cols:
            for r in rows_raw:
                rows.append([r.get(c, None) for c in cols])
        conf = "high"
        try:
            density = float(pm.get("data_density") or 0.0)
            if density < 0.9:
                conf = "medium"
        except Exception:
            density = None  # type: ignore
        tbl_block = {
            "type": "table",
            "title": None,
            "columns": cols,
            "rows": rows,
            "confidence": {"status": conf, "density": density if isinstance(density, (int, float)) else None, "source": "camelot+pandas"},
            "markdown": None,
            "markdown_provenance": None,
            "image_refs": [],
            "source": {
                "table_indices": [t.get("table_index")] if t.get("table_index") is not None else [],
                "page_indices": [t.get("page_index")] if t.get("page_index") is not None else [],
            },
        }
        out["blocks"].append(tbl_block)

    # Figures → figure blocks
    for f in section_data.get("figures", []) or []:
        cap = (f.get("caption") or f.get("ai_description") or "").strip() or None
        img_ref = f.get("image_path") or None
        try:
            page_idx = int(f.get("page", f.get("page_idx", -1)))
        except Exception:
            page_idx = -1
        fig_block = {
            "type": "figure",
            "title": None,
            "caption": cap,
            "alt": cap or "Figure",
            "image_ref": img_ref,
            "source": {"pages": [page_idx] if page_idx >= 0 else [], "block_ids": []},
        }
        out["blocks"].append(fig_block)

    return out

# --- Main Orchestration and CLI ---
@app.command()
def run(
    sections_json: Path = typer.Option(..., "--sections", help="Path to Stage 04 sections JSON.", exists=True),
    tables_json: Path = typer.Option(..., "--tables", help="Path to Stage 05 tables JSON.", exists=True),
    figures_json: Path = typer.Option(..., "--figures", help="Path to Stage 06 figures JSON.", exists=True),
    annotations_json: Optional[Path] = typer.Option(None, "--annotations", help="Optional: Path to Stage 01 annotations JSON."),
    output_dir: Path = typer.Option("data/results/pipeline", "-o", help="Parent directory for pipeline results."),
    summary_only: bool = typer.Option(False, "--summary-only", help="Emit merged_text snapshot without LLM calls."),
    include_images: bool = typer.Option(True, "--include-images/--no-include-images", help="Include images in LLM input"),
    allow_fallback: bool = typer.Option(False, "--allow-fallback", help="Allow text-only or pass-through fallbacks instead of failing early"),
    bundle: Optional[Path] = typer.Option(None, "--bundle", help="Debug: load consolidated sections JSON (keys: reflowed_sections or sections)")
):
    """
    Reflows document sections using multimodal context from previous stages.
    """
    console.print(f"[bold green]Starting Section Reflow (Stage 07)[/bold green]")
    run_id = get_run_id()
    diagnostics = []
    errors_count = 0
    warnings_count = 0
    import time
    t0 = time.monotonic()
    stage_start_ts = iso_now()
    resources = snapshot_resources("start")
    sampler = start_resource_sampler(float(os.getenv("SAMPLE_INTERVAL_SEC", "2"))) if os.getenv("ENABLE_RESOURCE_SAMPLING", "0").lower() in ("1","true","yes","y") else None
    try:
        if sampler and not gpu_metrics_available():
            diagnostics.append(make_event("07_reflow_section","info","gpu_metrics_unavailable","NVML not available; GPU metrics disabled",{}))
    except Exception:
        pass
    
    # --- Directory and Data Setup ---
    stage_output_dir = output_dir / "07_reflow_section"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    sections_to_process = consolidate_data(sections_json, tables_json, figures_json, annotations_json)

    # Optional: load or build FAISS index from Stage 01 annotations for similar text lookup
    ann_index = None; _ann_list = []
    try:
        if annotations_json and annotations_json.exists():
            stage01_dir = annotations_json.parent.parent  # .../01_annotation_processor
            idx, meta = load_ann_index(stage01_dir / 'annots_faiss')
            if idx is not None:
                ann_index = idx
                diagnostics.append(make_event('07_reflow_section','info','ann_index_loaded', f'Loaded FAISS index from {stage01_dir}', {}))
            else:
                _payload = json.load(open(annotations_json))
                _ann_list = _payload.get('annotations', []) or []
                if _ann_list:
                    ann_index, _ = build_ann_index(_ann_list)
                    diagnostics.append(make_event('07_reflow_section','info','ann_index_built', f'FAISS annotations index built: {len(_ann_list)} items', {}))
    except Exception as _ie:
        diagnostics.append(make_event('07_reflow_section','warning','ann_index_unavailable', str(_ie), {}))

    # Attach top-3 similar annotations (text-only) to each section (advisory)
    if ann_index is not None:
        for sec in sections_to_process:
            try:
                qtext = (str(sec.get('title', '')) + "\n" + str(sec.get('merged_text', '')))[:2000]
                sims = query_ann_index(ann_index, qtext, top_k=3)
                if sims:
                    # If we built from _ann_list, map indices to ids; else leave ids None
                    ids_scores = []
                    for i, score in sims:
                        aid = None
                        try:
                            if _ann_list:
                                aid = _ann_list[i].get('id')
                        except Exception:
                            aid = None
                        ids_scores.append({'id': aid, 'score': score})
                        try:
                            # add optional snippet
                            from extractor.pipeline.utils.ann_index import render_ann_snippet as _snip
                            import os as _os
                            if _ann_list:
                                _maxc = int(_os.getenv('ANN_SIMILAR_SNIPPET_CHARS','200'))
                                ids_scores[-1]['snippet'] = _snip(_ann_list[i], _maxc)
                        except Exception:
                            pass
                    sec['similar_annotations'] = ids_scores
            except Exception:
                pass
    
    if not sections_to_process:
        console.print("[yellow]No sections found to process. Exiting.[/yellow]"); return

    # --- Processing ---
    if summary_only:
        processed_sections = []
        for s in sections_to_process:
            # Emit summary-only payloads; do not call LLM
            sec_out = {
                **s,
                "reflowed_text": s.get("merged_text") or s.get("raw_text", ""),
                "ocr_corrections": {},
                "improvements_made": "summary-only (no LLM)",
                "reflow_status": "success_placeholder",
            }
            if STAGE07_DEBUG:
                sec_out["quick_summary"] = (s.get("merged_text") or s.get("raw_text", ""))[:280]
            processed_sections.append(sec_out)
    else:
        async def run_tasks():
            tasks = [reflow_section_with_llm(s, output_dir, include_images=include_images, allow_fallback=allow_fallback) for s in sections_to_process]
            return await tqdm_asyncio.gather(*tasks, desc="Reflowing Sections")
        processed_sections = asyncio.run(run_tasks())
    logger.debug(f"processed_sections_count={len(processed_sections)}")

    # --- Final Output ---
    # Attach resource samples
    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception:
        pass
    timings = build_stage_timings(stage_start_ts, t0)
    try:
        errors_count = sum(1 for d in diagnostics if d.get("severity") == "error")
        warnings_count = sum(1 for d in diagnostics if d.get("severity") == "warning")
    except Exception:
        pass
    final_output = {
        "timestamp": datetime.now().isoformat(),
        "source_files": {
            "sections": str(sections_json),
            "tables": str(tables_json),
            "figures": str(figures_json),
            "annotations": str(annotations_json) if annotations_json else None,
        },
        "status": "Completed",
        "section_count": len(processed_sections),
        "reflowed_sections": processed_sections,
        "run_id": run_id,
        "errors_count": errors_count,
        "warnings_count": warnings_count,
        "diagnostics": diagnostics,
        "timings": timings,
        "resources": resources,
    }
    
    output_path = json_output_dir / "07_reflowed.json"
    with open(output_path, 'w') as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)

    console.print(f"\n[bold green]✅ Section reflow complete.[/bold green]")
    console.print(f"   - Results saved to: [cyan]{output_path}[/cyan]")

@app.command("debug-bundle")
def debug_bundle(
    bundle: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False, readable=True, help="Consolidated sections JSON (keys: sections or reflowed_sections)"),
    output_dir: Path = typer.Option("data/results/pipeline", "-o", help="Results directory"),
    include_images: bool = typer.Option(True, "--include-images/--no-include-images"),
    allow_fallback: bool = typer.Option(False, "--allow-fallback"),
):
    """Run Stage 07 directly from a consolidated JSON bundle (debug only)."""
    stage_output_dir = output_dir / "07_reflow_section"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(parents=True, exist_ok=True)

    try:
        data = json.loads(bundle.read_text())
        sections_to_process = data.get('reflowed_sections') or data.get('sections') or []
        if not isinstance(sections_to_process, list):
            raise ValueError("bundle must contain list under 'sections' or 'reflowed_sections'")
    except Exception as e:
        typer.secho(f"Failed to load bundle: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    # Ensure minimal text fields for fallback if missing (source_text/merged_text)
    def _ensure_min_text_fields(sec: Dict[str, Any]) -> None:
        if not isinstance(sec, dict):
            return
        if 'source_text' in sec and 'merged_text' in sec:
            return
        blocks = sec.get('blocks') or []
        if isinstance(blocks, list):
            # Build source_text and merged_text similar to consolidate_data()
            parts = []
            merged_parts = []
            for b in blocks:
                txt = (b.get('text') or '').strip()
                if not txt:
                    continue
                parts.append(txt)
                lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
                if lines:
                    merged_parts.append(' '.join(lines))
            if 'source_text' not in sec:
                sec['source_text'] = "\n".join(parts)
            if 'merged_text' not in sec:
                sec['merged_text'] = "\n\n".join(merged_parts)

    for s in sections_to_process:
        _ensure_min_text_fields(s)

    # initialize minimal diagnostics/timing like run()
    run_id = get_run_id()
    diagnostics: list[dict] = []
    errors_count = 0
    warnings_count = 0
    from time import monotonic as _monotonic
    stage_start_ts = iso_now()
    t0 = _monotonic()
    resources = snapshot_resources("start")
    sampler = None

    async def run_tasks():
        tasks = [reflow_section_with_llm(s, output_dir, include_images=include_images, allow_fallback=allow_fallback) for s in sections_to_process]
        return await tqdm_asyncio.gather(*tasks, desc="Reflowing Sections (debug)")
    processed_sections = asyncio.run(run_tasks())

    # Attach resource samples
    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception:
        pass
    timings = build_stage_timings(stage_start_ts, t0)
    try:
        errors_count = sum(1 for d in diagnostics if d.get("severity") == "error")
        warnings_count = sum(1 for d in diagnostics if d.get("severity") == "warning")
    except Exception:
        pass
    final_output = {
        "timestamp": datetime.now().isoformat(),
        "status": "Completed",
        "section_count": len(processed_sections),
        "reflowed_sections": processed_sections,
        "run_id": run_id,
        "errors_count": errors_count,
        "warnings_count": warnings_count,
        "diagnostics": diagnostics,
        "timings": timings,
        "resources": resources,
    }
    output_path = json_output_dir / "07_reflowed.json"
    output_path.write_text(json.dumps(final_output, indent=2, ensure_ascii=False))
    console.print(f"[green]Saved debug reflow to:[/green] {output_path}")

if __name__ == "__main__":
    app()
