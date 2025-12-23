#!/usr/bin/env python3
"""
Pipeline Stage: LLM-Based Section Reflow (offline)

This script is the final text processing stage. It runs offline (no DB access)
to perform a powerful hybrid search for relevant annotations. This rich,
dynamically-fetched context is then used to guide a VLM in reflowing and
improving the section's content. All database and search logic is self-contained.
"""

import asyncio
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
# (dotenv loaded by caller/debug harness)
from loguru import logger
from extractor.pipeline.utils.reliability import log_stage_error
from rich.console import Console
# Router-only SciLLM policy (no direct scillm imports in steps)
from tqdm.asyncio import tqdm_asyncio

from extractor.core.schema.unified_document import SourceType
from extractor.pipeline.utils.ann_index import build_ann_index, load_ann_index, query_ann_index
from extractor.pipeline.utils.diagnostics import (
    build_stage_timings,
    classify_llm_error,
    get_run_id,
    gpu_metrics_available,
    iso_now,
    make_event,
    snapshot_resources,
    start_resource_sampler,
    stop_resource_sampler,
)
from extractor.pipeline.utils.image_io import (
    get_annotation_image_b64,
    get_figure_image_b64,
    get_section_image_b64,
    get_table_image_b64,
)
from extractor.pipeline.utils.json_utils import (
    MAX_TOKENS_IMAGE,
    STOP_FENCES,
    STRICT_JSON_GUARD,
    clean_json_string,
    parse_json_strict,
    restrict_top_level_keys,
)
from extractor.pipeline.utils.prompt_loader import load_prompt

# Extracted reflow utilities (Phase 2 refactoring)
from extractor.pipeline.utils.reflow import (
    # Tables
    sanitize_table_cell as _sanitize_table_cell,
    compute_table_confidence as _table_confidence,
    compute_table_merges as _compute_table_merges,
    build_table_block_from_stage05 as _build_table_block_from_stage05,
    df_map as _df_map,
    normalize_table_text as _normalize_table_text,
    # Layout
    iou_rect as _iou_rect,
    horizontal_iou as _h_iou,
    build_figure_block_from_stage06 as _build_figure_block_from_stage06,
    apply_layout_ordering as _apply_layout_ordering,
    # LLM Helpers
    extract_router_content as _router_content,
    content_to_json_dict as _content_to_json_dict,
    direct_scillm_json as _direct_scillm_json,
    get_usage_field as _usage_get,
    # Prompts
    build_reflow_prompt,
    build_compact_prompt as _build_compact_prompt,
    build_compact_prompt_simple as _build_compact_prompt_simple,
    # Data Loader
    consolidate_data,
    merge_section_tables as _merge_section_tables,
)
from extractor.pipeline.utils.reflow.section_reflow import reflow_section_with_llm
from extractor.pipeline.utils.reflow.runner import run


# extract_content no longer used here; keep JSON-mode path only
from extractor.pipeline.utils.log_utils import sanitize_messages_for_return  # noqa: E402
from extractor.pipeline.utils.metrics_logger import log_metric  # noqa: E402
from extractor.pipeline.utils.model_params import (  # noqa: E402
    build_chat_extras,
)
# SciLLM client adapter wrappers are not used in Stage 07 per policy (Router-only)
from extractor.pipeline.utils.text_utils import sanitize_text  # noqa: E402
from extractor.pipeline.utils.unified_conversion import build_unified_document_from_reflow  # noqa: E402
from extractor.pipeline.utils.vision import preflight_vision_support  # noqa: E402
from extractor.pipeline.utils.step_sanity import run_step_sanity
from extractor.pipeline.steps.scillm_preflight_validator import require_scillm_preflight

# Model selection (place imports at top to satisfy E402)
from extractor.pipeline.utils.model_select import get_vlm_model, get_text_model  # noqa: E402
from extractor.pipeline.utils.debug_utils import ensure_logs_dir, time_block, summarize_messages, log_timing  # noqa: E402


from extractor.pipeline.utils.scillm_router import get_text_router  # Router-only policy  # noqa: E402




async def _direct_compact_fallback(
    section_data: Dict[str, Any],
    *,
    results_base_dir: Path,
    timeout: int,
) -> Optional[str]:
    """Low-context direct call when Router attempts fail."""
    try:
        compact_user = _build_compact_prompt_simple(
            section_data,
            text_char_cap=int(os.getenv("STAGE07_CONTEXT_CHARS", "1200")),
        )
    except Exception as exc:
        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
        raise
        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
        raise
        log_stage_error('07_reflow_section', exc, {'context': '07'})
        raise
        return None
    messages_simple = [
        {"role": "system", "content": "You respond with JSON only — no code fences, no prose."},
        {"role": "user", "content": compact_user},
    ]
    content = await _direct_scillm_json(
        messages_simple,
        response_format={"type": "json_object"},
        max_tokens=min(STAGE07_MAX_TOKENS, 1024),
        timeout=timeout,
    )
    if content is not None:
        try:
            logs_dir = ensure_logs_dir(results_base_dir, "07_reflow_section")
            sid_str = str(section_data.get("id", "section"))
            (logs_dir / f"response_compact_direct_{sid_str}.json").write_text(
                json.dumps(content, ensure_ascii=False, indent=2, default=str)
                if isinstance(content, (dict, list))
                else str(content)
            )
        except Exception as exc:
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07'})
            raise
            pass
    return content
# Shared helper: table confidence heuristic (0.0–1.0)
def sanity() -> int:
    return run_step_sanity(STEP_NAME)

# Hybrid search removed; Stage 07 runs fully offline

# Text embedding model (lazy-loaded)
text_embedding_model: Any = None
from extractor.pipeline.utils.embeddings import ensure_embedder as _ensure_embedder  # noqa: E402

# removed local embedder implementation

# Configuration from environment variables
# Resolve the concrete model inside run() so we can avoid requiring a VLM when images are disabled.
LLM_MODEL: str | None = None
MAX_CONCURRENT_CALLS = int(os.getenv("MAX_CONCURRENT_LLM_CALLS", 3))
LLM_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_CALLS)
SEMANTIC_TOP_K = int(os.getenv("SEMANTIC_ANNOTATION_TOP_K", 5))
TABLE_CONF_THRESHOLD = float(os.getenv("STAGE07_TABLE_CONFIDENCE_THRESHOLD", "0.6"))
INCLUDE_FIGURE_IMAGES = os.getenv("STAGE07_INCLUDE_FIGURES", "false").lower() in (
    "1",
    "true",
    "yes",
    "y",
)
MAX_ANNOTATION_IMAGES = int(os.getenv("STAGE07_MAX_ANNOTATION_IMAGES", "2"))
# Default to including the section image when available
ATTACH_SECTION_IMAGE = os.getenv("STAGE07_ATTACH_SECTION_IMAGE", "1").lower() in (
    "1",
    "true",
    "yes",
    "y",
)
SCHEMA_MODE = (
    os.getenv("STAGE07_SCHEMA_MODE", "reflow_json").strip().lower()
)  # "text" | "reflow_json"
TABLE_LLM_NORMALIZE = os.getenv("STAGE07_TABLE_LLM_NORMALIZE", "true").lower() in (
    "1",
    "true",
    "yes",
    "y",
)
FIGURE_FALLBACK_ENABLED = os.getenv("STAGE07_FIGURE_FALLBACK", "false").lower() in (
    "1",
    "true",
    "yes",
    "y",
)
# Max output tokens for strict JSON responses (can be tuned via env)
STAGE07_MAX_TOKENS = int(os.getenv("STAGE07_MAX_TOKENS", "2048"))
# Router-only SciLLM policy: disable any native client fallbacks
ROUTER_ONLY = True

# Layout sketch consumption (quick win)
USE_LAYOUT_SKETCH = os.getenv("STAGE07_USE_LAYOUT_SKETCH", "true").lower() in (
    "1",
    "true",
    "yes",
    "y",
)
LAYOUT_CONF_THRESH = float(os.getenv("STAGE07_LAYOUT_CONF_THRESH", "0.75"))
OMIT_IMAGES_IF_CONFIDENT = os.getenv("STAGE07_OMIT_IMAGES_IF_CONFIDENT", "true").lower() in (
    "1",
    "true",
    "yes",
    "y",
)

# Visual proof toggles
STAGE07_VISUAL_PROOF = os.getenv("STAGE07_VISUAL_PROOF", "").lower() in ("1", "true", "yes", "y")
STAGE07_SOURCE_PDF = os.getenv("STAGE07_SOURCE_PDF", "").strip() or None

PROMPT_REFLOW = load_prompt("07_reflow_section")


# --- Core LLM and Prompting Functions ---


def build_section_context_text(section: dict[str, Any]) -> str:
    """Compose concise textual context including tables, figures, and the most relevant annotations (with text)."""
    lines: list[str] = []
    title = sanitize_text(section.get("title", "Untitled"))
    level = section.get("level", 0)
    page_start = section.get("page_start")
    page_end = section.get("page_end")
    lines.append(f"Section: {title} (level {level}) pages {page_start}–{page_end}")
    # If a deterministic layout sketch is present, include a compact summary
    try:
        sk = section.get("layout_sketch") or {}
        if sk:
            # Prefer human-readable instructive DSL if present
            dsl = (sk.get("instructive_dsl") or "").strip()
            if dsl:
                lines.append("LayoutSketch (instructive):")
                # Cap to protect tokens; leave the rest to the model’s reasoning
                lines.append(dsl if len(dsl) <= 1200 else (dsl[:1200] + " …"))
            else:
                grid = sk.get("grid", 12)
                elems = sk.get("elements") or []
                text_n = sum(1 for e in elems if e.get("kind") == "text")
                table_n = sum(1 for e in elems if e.get("kind") == "table")
                figure_n = sum(1 for e in elems if e.get("kind") == "figure")
                qs = (sk.get("quick_summary") or "").strip()
                lines.append(f"LayoutSketch: grid={grid} text={text_n} tables={table_n} figures={figure_n}")
                if qs:
                    lines.append(f"SketchSummary: {qs}")
    except Exception as exc:
        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
        raise
        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
        raise
        log_stage_error('07_reflow_section', exc, {'context': '07'})
        raise
        pass
    # Include a concise JSON-like section summary to ground the LLM
    sec_num = section.get("metadata", {}).get("section_number") or section.get("section_number")
    sec_hash = section.get("metadata", {}).get("section_hash") or section.get("section_hash")
    lines.append("Section JSON Summary:")
    lines.append(
        json.dumps(
            {
                "id": section.get("id"),
                "title": title,
                "level": level,
                "section_number": sec_num,
                "section_hash": sec_hash,
                "page_start": page_start,
                "page_end": page_end,
                "blocks_count": len(section.get("blocks", [])),
            },
            ensure_ascii=False,
        )
    )

    # Inject compact layout prior (from 06b) when present
    try:
        lsk = section.get("layout_sketch") or {}
        if isinstance(lsk, dict) and lsk:
            conf = (lsk.get("conf") or {}).get("ordering")
            cols = lsk.get("columns") or []
            dsl = lsk.get("flow_stream") or ""
            # Keep DSL compact to protect token budget
            dsl_snippet = dsl if len(dsl) <= 1200 else (dsl[:1200] + " …")
            lines.append("Layout Prior:")
            lines.append(
                json.dumps(
                    {
                        "ordering_conf": conf,
                        "columns": cols,  # grid bands [{id,x0,x1}]
                        "dsl": dsl_snippet,
                    },
                    ensure_ascii=False,
                )
            )
    except Exception as exc:
        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
        raise
        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
        raise
        log_stage_error('07_reflow_section', exc, {'context': '07'})
        raise
        pass

    raw_text = sanitize_text(
        section.get("source_text") or section.get("merged_text") or section.get("raw_text", "")
    )
    if raw_text:
        snippet = raw_text if len(raw_text) <= 6000 else raw_text[:6000] + " ..."
        lines.append("Source Text:")
        lines.append(snippet)

    # Tables summary
    tables = section.get("tables", [])
    if tables:
        lines.append(f"Tables: {len(tables)}")
        merge_hint = False
        for t in tables[:3]:
            pm = t.get("pandas_metrics", {}) or {}
            cols = pm.get("columns", [])
            shape = pm.get("shape", [])
            density = pm.get("data_density")
            lines.append(
                f"- Table idx {t.get('table_index')}: shape={shape}, columns={cols}, density={density}"
            )
            rows = t.get("pandas_df", [])[:3] or t.get("pandas_df_dict", [])[:3]
            if rows:
                try:
                    lines.append(f"  sample_rows: {json.dumps(rows, ensure_ascii=False)[:500]}")
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
                try:
                    def _normalize_cell(val: Any) -> str:
                        if val is None:
                            return ""
                        text = str(val)
                        text = text.replace("\u00a0", " ")
                        text = re.sub(r"\s+", " ", text).strip()
                        return text

                    normalized_preview: list[list[str]] = []
                    for r in rows:
                        if isinstance(r, dict):
                            normalized_preview.append([_normalize_cell(r.get(c, "")) for c in cols])
                        elif isinstance(r, list):
                            normalized_preview.append([_normalize_cell(v) for v in r])
                    if normalized_preview:
                        lines.append(
                            f"  normalized_rows_preview: {json.dumps(normalized_preview, ensure_ascii=False)[:500]}"
                        )
                        lines.append(
                            "  normalization_hint: Remove only spurious spaces within tokens (e.g., 'Descripti on' -> 'Description', 'in in in ou t' -> 'in/in/in/out'). Do not alter spelling beyond deleting those extra spaces."
                        )
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
            try:
                rows_count = int((pm.get("shape") or [0])[0] or 0)
                if rows_count <= 1:
                    merge_hint = True
            except Exception as exc:
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                raise
                log_stage_error('07_reflow_section', exc, {'context': '07'})
                raise
                pass
        if len(tables) > 1:
            merge_hint = True
        # Optional: enforce exact column hints via env for deterministic reflow
        try:
            import os as _os

            forced = _os.getenv("STAGE07_FORCE_TABLE_COLUMNS", "").strip()
            if forced:
                # comma-separated list
                cols_hint = [c.strip() for c in forced.split(",") if c.strip()]
                if cols_hint:
                    lines.append("Table Hints:")
                    lines.append(f"columns_exact: {json.dumps(cols_hint, ensure_ascii=False)}")
        except Exception as exc:
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07'})
            raise
            pass
        if merge_hint:
            lines.append(
                "Table Merge Directive: If Stage 05 produced header/body fragments of the same table,"
                " merge them into one logical table block. Strip embedded newlines from header text,"
                " keep cell content verbatim, and set the table title to begin with 'INFERRED:'"
                " based on nearby narrative context."
            )

    # Figures summary
    figures = section.get("figures", [])
    if figures:
        lines.append(f"Figures: {len(figures)}")
        for f in figures[:3]:
            desc = f.get("ai_description", "")
            imgp = f.get("image_path") or ""
            lines.append(f"- Figure {f.get('figure_id')}: {desc[:300]} (image_path={imgp})")

    # Annotations on the same pages (include by default) with interpretation if available
    def _blocks_to_text(blocks: list[dict[str, Any]], max_chars: int = 400) -> str:
        parts: list[str] = []
        for blk in blocks or []:
            for ln in blk.get("lines", []):
                for sp in ln.get("spans", []):
                    t = sanitize_text(sp.get("text") or "")
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
            lines.append(
                json.dumps(
                    {
                        "id": a.get("id"),
                        "type": a_type,
                        "similarity": sim,
                        "interpretation": {
                            "title": interp.get("title"),
                            "summary": interp.get("summary"),
                            "entities": interp.get("entities"),
                            "labels": interp.get("labels"),
                        },
                        "inside": inside,
                        "above": above,
                        "below": below,
                    },
                    ensure_ascii=False,
                )
            )

    return "\n".join(lines)


# --- JSON normalization helper (dict-or-string) ---

def _structured_fallback(section_data: dict[str, Any]) -> dict[str, Any]:
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

    out: dict[str, Any] = {
        "section_id": section_data.get("id") or section_data.get("section_id") or "section",
        "title": section_data.get("title") or section_data.get("display_title") or "Untitled",
        "blocks": [],
    }

    # Merge consecutive Text blocks into paragraphs
    para_text: list[str] = []
    para_pages: list[int] = []
    para_ids: list[str] = []
    for b in section_data.get("blocks", []) or []:
        btype = b.get("block_type") or b.get("type")
        if btype == "Text":
            t = _clean_lines(b.get("text") or "")
            if t:
                para_text.append(t)
                try:
                    para_pages.append(int(b.get("page", b.get("page_idx", -1))))
                except Exception as exc:
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
                    raise
                    log_stage_error('07_reflow_section', exc, {'context': '07'})
                    raise
                    pass
                if b.get("id"):
                    para_ids.append(str(b.get("id")))
            continue
        # flush paragraph when hitting a non-text block
        if para_text:
            out["blocks"].append(
                {
                    "type": "paragraph",
                    "text": " ".join(para_text),
                    "source": {
                        "pages": sorted(
                            list({p for p in para_pages if isinstance(p, int) and p >= 0})
                        ),
                        "block_ids": para_ids,
                    },
                }
            )
            para_text, para_pages, para_ids = [], [], []
        # carry through other block types only as markers (figures handled below)
    if para_text:
        out["blocks"].append(
            {
                "type": "paragraph",
                "text": " ".join(para_text),
                "source": {
                    "pages": sorted(list({p for p in para_pages if isinstance(p, int) and p >= 0})),
                    "block_ids": para_ids,
                },
            }
        )

    # Tables → table blocks using pandas data
    for t in section_data.get("tables", []) or []:
        tbl_block = _build_table_block_from_stage05(t)
        if tbl_block:
            out["blocks"].append(tbl_block)

    # Figures → figure blocks
    for f in section_data.get("figures", []) or []:
        cap = (f.get("caption") or f.get("ai_description") or "").strip() or None
        img_ref = f.get("image_path") or None
        try:
            page_idx = int(f.get("page", f.get("page_idx", -1)))
        except Exception as exc:
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
            raise
            log_stage_error('07_reflow_section', exc, {'context': '07'})
            raise
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
def debug_bundle(
    bundle: Path,
    output_dir: Path = Path("data/results/pipeline"),
    include_images: bool = True,
    allow_fallback: bool = False,
    request_timeout: int = 120,
):
    """Run Stage 07 directly from a consolidated JSON bundle (debug only)."""
    stage_output_dir = output_dir / "07_reflow_section"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(parents=True, exist_ok=True)

    try:
        data = json.loads(bundle.read_text())
        sections_to_process = data.get("reflowed_sections") or data.get("sections") or []
        if not isinstance(sections_to_process, list):
            raise ValueError("bundle must contain list under 'sections' or 'reflowed_sections'")
    except Exception as exc:
        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
        raise
        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
        raise
        log_stage_error('07_reflow_section', exc, {'context': '07'})
        raise
        logger.error(f"Failed to load bundle: {e}")
        raise ValueError(f"Failed to load bundle: {e}")

    # Ensure minimal text fields for fallback if missing (source_text/merged_text)
    def _ensure_min_text_fields(sec: dict[str, Any]) -> None:
        if not isinstance(sec, dict):
            return
        if "source_text" in sec and "merged_text" in sec:
            return
        blocks = sec.get("blocks") or []
        if isinstance(blocks, list):
            # Build source_text and merged_text similar to consolidate_data()
            parts = []
            merged_parts = []
            for b in blocks:
                txt = (b.get("text") or "").strip()
                if not txt:
                    continue
                parts.append(txt)
                lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
                if lines:
                    merged_parts.append(" ".join(lines))
            if "source_text" not in sec:
                sec["source_text"] = "\n".join(parts)
            if "merged_text" not in sec:
                sec["merged_text"] = "\n\n".join(merged_parts)

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
        tasks = [
            reflow_section_with_llm(
                s,
                output_dir,
                include_images=include_images,
                allow_fallback=allow_fallback,
                llm_timeout=request_timeout,
            )
            for s in sections_to_process
        ]
        return await tqdm_asyncio.gather(*tasks, desc="Reflowing Sections (debug)")

    processed_sections = asyncio.run(run_tasks())

    # Attach resource samples
    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception as exc:
        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
        raise
        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
        raise
        log_stage_error('07_reflow_section', exc, {'context': '07'})
        raise
        pass
    timings = build_stage_timings(stage_start_ts, t0)
    try:
        errors_count = sum(1 for d in diagnostics if d.get("severity") == "error")
        warnings_count = sum(1 for d in diagnostics if d.get("severity") == "warning")
    except Exception as exc:
        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
        raise
        log_stage_error('07_reflow_section', exc, {'context': '07_reflow_retry'})
        raise
        log_stage_error('07_reflow_section', exc, {'context': '07'})
        raise
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
    if os.getenv("DRY_RUN", "0").lower() not in {"1","true","yes","y"}:
        output_path.write_text(json.dumps(final_output, indent=2, ensure_ascii=False))
    else:
        console.print("[yellow]DRY_RUN=1 → skipped writing 07_reflowed.json (debug path)[/yellow]")
    console.print(f"[green]Saved debug reflow to:[/green] {output_path}")


## CLI removed: import and call run(...), or use a debug harness.


## __main__ added above for convenience


# Helper for tests/smoke and for message shaping assertions
def build_reflow_request_messages(
    section_data: dict[str, Any],
    results_base_dir: Path,
    *,
    include_images: bool,
    model: str,
    context_text: str,
) -> list[dict[str, Any]]:
    # Enforce text-only for Stage 07
    include_images = False
    def _is_gemini(m: str) -> bool:
        return "gemini" in (m or "").lower()

    # Collect images similar to the main function (section, low-conf table, optional figure, one annotation)
    image_blocks: list[dict[str, Any]] = []
    if include_images:
        # Section visual
        sec_b64 = get_section_image_b64(section_data, results_base_dir)
        if sec_b64:
            image_blocks.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{sec_b64}"}}
            )

        # Low-confidence table image
        for t in section_data.get("tables", []) or []:
            if _table_confidence(t) < TABLE_CONF_THRESHOLD:
                tb64 = get_table_image_b64(t, results_base_dir)
                if tb64:
                    image_blocks.append(
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{tb64}"}}
                    )
                    break
        # One figure image
        figs = section_data.get("figures", []) or []
        if figs:
            fb64 = get_figure_image_b64(figs[0], results_base_dir)
            if fb64:
                image_blocks.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{fb64}"}}
                )
        # One annotation image
        anns = section_data.get("annotations", []) or []
        if anns:
            ab64 = get_annotation_image_b64(anns[0], results_base_dir)
            if ab64:
                image_blocks.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{ab64}"}}
                )

    # JSON guard
    system_text = (
        "You are a strict JSON reflow engine. Return ONLY a JSON object with keys: "
        "reflowed_json, ocr_corrections, improvements_made, summary. No code fences. "
        "Requirements: reflowed_json.blocks must preserve reading _order and include: "
        "(a) a single merged table block when tables are fragmented/continued. The table title MUST start with 'INFERRED:' (e.g., INFERRED: …). Use the nearby text to form a concise title but always prefix with INFERRED:. The table must include 'columns' and 'rows' consistent with provided context. When column hints are provided in context, use those exact column names verbatim and in _order; do NOT rename or substitute synonyms. Do not alter cell values; "
        "(b) a figure block with a non-empty title (literal or INFERRED), short caption, and image_ref when applicable. "
        "Always provide ocr_corrections and improvements_made; include summary."
    )
    if _is_gemini(model):
        # Place guard at the start of user's first text part; use standard 'text' + 'image_url' parts
        parts = [{"type": "text", "text": f"{system_text}\n\n{context_text}"}]
        parts.extend(image_blocks)
        return [{"role": "user", "content": parts}]
    else:
        parts = [{"type": "text", "text": context_text}]
        parts.extend(image_blocks)
        return [
            {"role": "system", "content": system_text},
            {"role": "user", "content": parts},
        ]
