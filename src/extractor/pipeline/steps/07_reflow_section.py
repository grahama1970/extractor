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
try:
    from tenacity import retry, stop_after_attempt, wait_random_exponential
except ImportError:  # minimal fallback: no retry
    def retry(*args, **kwargs):
        def _wrap(fn):
            return fn
        return _wrap
    def stop_after_attempt(*args, **kwargs):
        return None
    def wait_random_exponential(*args, **kwargs):
        return None
from extractor.core.services.utils.json_utils import clean_json_string
from extractor.pipeline.utils.image_io import (
    get_section_image_b64,
    get_table_image_b64,
    get_figure_image_b64,
    get_annotation_image_b64,
)
from extractor.pipeline.utils.diagnostics import start_resource_sampler, stop_resource_sampler, get_run_id, iso_now, make_event, snapshot_resources, build_stage_timings, classify_llm_error, gpu_metrics_available
from extractor.pipeline.utils.litellm_call import litellm_call
from extractor.pipeline.utils.vision import preflight_vision_support
from extractor.pipeline.utils.ann_index import build_ann_index, query_ann_index, load_ann_index

# --- Initialization & Configuration ---

if not load_dotenv(find_dotenv(), override=True):
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
LLM_MODEL = os.getenv("LITELLM_VLM_MODEL", "openai/gpt-5")
MAX_CONCURRENT_CALLS = int(os.getenv("MAX_CONCURRENT_LLM_CALLS", 3))
LLM_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_CALLS)
SEMANTIC_TOP_K = int(os.getenv("SEMANTIC_ANNOTATION_TOP_K", 5))


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

def build_section_context_text(section: Dict[str, Any]) -> str:
    """Compose concise textual context including tables, figures, and the most relevant annotations (with text)."""
    lines: List[str] = []
    title = section.get("title", "Untitled")
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

    raw_text = section.get("source_text") or section.get("merged_text") or section.get("raw_text", "")
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
                    t = (sp.get("text") or "").strip()
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





@retry(wait=wait_random_exponential(min=1, max=30), stop=stop_after_attempt(3))
async def reflow_section_with_llm(section_data: Dict[str, Any], results_base_dir: Path, *, include_images: bool, allow_fallback: bool) -> Dict[str, Any]:
    """Reflow a section using multimodal context (section/table/figure/annotation) and return structured JSON."""
    try:
        sec_diags = []
        # Decide if the model supports multimodal inputs
        supports_vision = any(
            kw in (LLM_MODEL or "").lower()
            for kw in ("gpt-4o", "gpt-4.1", "gpt-4-vision", "claude-3", "gemini", "llava", "qwen-vl", "grok-vision")
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
                if not ok:
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
            # Table images (up to 2)
            for t in section_data.get("tables", [])[:2]:
                tb64 = get_table_image_b64(t, results_base_dir)
                if tb64:
                    try:
                        sec_diags.append(make_event("07_reflow_section","info","table_image_attached","Included table image", {"table_index": t.get("table_index") }))
                    except Exception:
                        pass
                if tb64:
                    image_blocks.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{tb64}"}})
            # Figure images (up to 2)
            for f in section_data.get("figures", [])[:2]:
                fb64 = get_figure_image_b64(f, results_base_dir)
                if fb64:
                    try:
                        sec_diags.append(make_event("07_reflow_section","info","figure_image_attached","Included figure image", {"figure_id": f.get("figure_id") }))
                    except Exception:
                        pass
                if fb64:
                    image_blocks.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{fb64}"}})
            # Annotation images (up to 2)
            for a in section_data.get("annotations", [])[:2]:
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

        system_prompt = dedent("""
        You are a technical editor. Given raw PDF-extracted section text plus structured context (tables with pandas metrics, figure descriptions, and nearby annotations), produce a clean Markdown reflow of the section.
        - Fix broken words, hyphenation across lines, and common OCR errors.
        - Keep semantics but remove duplicated headers/footers.
        - Respect original table intent; do not invent data. If tables are present, incorporate them as Markdown tables only if reliable; otherwise summarize them.

        Output strictly JSON with keys:
          - "reflowed_text": "string (Markdown)"
          - "ocr_corrections": {"erroneous": "corrected", ...}
          - "improvements_made": "short description of the fixes"
          - "summary": "1–3 sentences summarizing the section content"
        Do not include explanations outside JSON.
        """).strip()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        # Build Responses API user content (text + images)
        responses_user_content: list[dict[str, Any]] = [{"type": "input_text", "text": context_text}]
        if include_images:
            sec_b64 = get_section_image_b64(section_data, results_base_dir)
            if sec_b64:
                responses_user_content.append({"type": "input_image", "image_url": f"data:image/png;base64,{sec_b64}"})
            for t in section_data.get("tables", [])[:2]:
                tb64 = get_table_image_b64(t, results_base_dir)
                if tb64:
                    try:
                        sec_diags.append(make_event("07_reflow_section","info","table_image_attached","Included table image", {"table_index": t.get("table_index") }))
                    except Exception:
                        pass
                if tb64:
                    responses_user_content.append({"type": "input_image", "image_url": f"data:image/png;base64,{tb64}"})
            for f in section_data.get("figures", [])[:2]:
                fb64 = get_figure_image_b64(f, results_base_dir)
                if fb64:
                    try:
                        sec_diags.append(make_event("07_reflow_section","info","figure_image_attached","Included figure image", {"figure_id": f.get("figure_id") }))
                    except Exception:
                        pass
                if fb64:
                    responses_user_content.append({"type": "input_image", "image_url": f"data:image/png;base64,{fb64}"})
            for a in section_data.get("annotations", [])[:2]:
                ab64 = get_annotation_image_b64(a, results_base_dir)
                if ab64:
                    responses_user_content.append({"type": "input_image", "image_url": f"data:image/png;base64,{ab64}"})

        # LLM call: prefer OpenAI Responses API for GPT-5 with reasoning
        try:
            from litellm import aresponses as _aresponses  # type: ignore
        except Exception:
            _aresponses = None  # type: ignore
        # Disable Responses API path for simplicity/compatibility
        _aresponses = None
        try:
            results = await litellm_call([{"model": LLM_MODEL, "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ], "response_format": {"type": "json_object"}, "max_tokens": 1200, "timeout": 60, "stream": False}], wrap_json=False, concurrency=1, desc="Reflow Section")
            resp = results[0] if results else ""
        except Exception as e:
            if not allow_fallback:
                typer.secho(f"Stage 07 LLM call failed: {e}", fg=typer.colors.RED)
                raise
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
            if not allow_fallback:
                typer.secho("Stage 07: LLM returned empty content.", fg=typer.colors.RED)
                raise RuntimeError("LLM returned empty content")
            logger.warning("Reflow LLM returned empty content; falling back to pass-through text.")
            try:
                sec_diags.append(make_event("07_reflow_section","warning","llm_empty_content","LLM returned empty content", {}))
            except Exception:
                pass
            base_text = (
                section_data.get("merged_text")
                or section_data.get("source_text")
                or section_data.get("raw_text", "")
            )
            out = {
                **section_data,
                "reflowed_text": base_text,
                "ocr_corrections": {},
                "improvements_made": "Fallback: empty LLM output",
                "reflow_status": "fallback",
            }
            # attach per-section diagnostics
            try:
                md = out.setdefault("metadata", {})
                md.setdefault("diagnostics", []).extend(sec_diags)
            except Exception:
                pass
            if STAGE07_DEBUG:
                out["quick_summary"] = (section_data.get("merged_text") or section_data.get("raw_text", ""))[:280]
            return out

        cleaned = clean_json_string(content)
        try:
            result = json.loads(cleaned) if isinstance(cleaned, str) else cleaned
            if not isinstance(result, dict):
                raise ValueError("LLM JSON not an object")
        except Exception:
            logger.warning("Invalid JSON from LLM; using raw text fallback")
            try:
                sec_diags.append(make_event("07_reflow_section","warning","llm_invalid_json","LLM returned invalid JSON", {}))
            except Exception:
                pass
            base_text = (
                section_data.get("merged_text")
                or section_data.get("source_text")
                or section_data.get("raw_text", "")
            )
            out = {
                **section_data,
                "reflowed_text": base_text,
                "ocr_corrections": {},
                "improvements_made": "Fallback: invalid LLM JSON",
                "reflow_status": "fallback",
            }
            # attach per-section diagnostics
            try:
                md = out.setdefault("metadata", {})
                md.setdefault("diagnostics", []).extend(sec_diags)
            except Exception:
                pass
            try:
                md = out.setdefault("metadata", {})
                md.setdefault("diagnostics", []).extend(sec_diags)
            except Exception:
                pass
            if STAGE07_DEBUG:
                out["quick_summary"] = (section_data.get("merged_text") or section_data.get("raw_text", ""))[:280]
            return out

        out = {**section_data}
        out.update({
            "reflowed_text": result.get("reflowed_text", section_data.get("raw_text", "")),
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
        if not allow_fallback:
            typer.secho(f"Stage 07: LLM call failed: {e}", fg=typer.colors.RED)
            raise
        try:
            info = classify_llm_error(e)
            sec_diags.append(make_event("07_reflow_section","error", info["code"], info["message"], {}))
        except Exception:
            pass
        logger.warning(f"Reflow LLM call failed; using fallback: {e}")
        base_text = (
            section_data.get("merged_text")
            or section_data.get("source_text")
            or section_data.get("raw_text", "")
        )
        out = {
            **section_data,
            "reflowed_text": base_text,
            "ocr_corrections": {},
            "improvements_made": "Fallback: exception during LLM call",
            "reflow_status": "fallback",
        }
        try:
            md = out.setdefault("metadata", {})
            md.setdefault("diagnostics", []).extend(sec_diags)
        except Exception:
            pass
        if STAGE07_DEBUG:
            out["quick_summary"] = (section_data.get("merged_text") or section_data.get("raw_text", ""))[:280]
        return out

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