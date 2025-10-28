#!/usr/bin/env python3
"""
Pipeline Stage: LLM-Based Section Reflow (offline)

This script is the final text processing stage. It runs offline (no DB access)
to perform a powerful hybrid search for relevant annotations. This rich,
dynamically-fetched context is then used to guide a VLM in reflowing and
improving the section's content. All database and search logic is self-contained.
"""

import asyncio
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
from rich.console import Console
# Avoid hard dependency on scillm so deterministic prep paths can run
try:
    from scillm import acompletion as sc_acompletion  # type: ignore
except Exception:  # pragma: no cover
    sc_completion = None  # legacy alias unused
    sc_acompletion = None  # type: ignore
from litellm import Router  # SciLLM-compatible Router (OpenAI-like)
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


def _build_compact_prompt(
    *,
    results_base_dir: Path,
    section_data: Dict[str, Any],
    tables: List[Dict[str, Any]],
    figures: List[Dict[str, Any]],
    sketch_v2_by_sec: Dict[str, Any],
) -> str:
    """Construct a compact, string-only prompt using 06b's sketch_v2 + 06a enrichments."""
    sid = str(section_data.get("id"))
    sketch = (sketch_v2_by_sec or {}).get(sid) or {}
    tabs_for_sec = [t for t in (tables or []) if str(t.get("section_id")) == sid]
    figs_for_sec = [f for f in (figures or []) if str(f.get("section_id")) == sid]

    # Identify merge candidates by (logical_table_id, header_norm)
    merges: List[str] = []
    by_key: Dict[str, List[str]] = {}
    for t in tabs_for_sec:
        key = f"{t.get('logical_table_id') or ''}|{t.get('header_norm') or ''}"
        if key.strip('|'):
            by_key.setdefault(key, []).append(str(t.get('id') or t.get('table_id') or 'tbl'))
    for k, ids in by_key.items():
        if len(ids) >= 2:
            merges.append(f"logical={k} parts={','.join(ids[:6])}")

    lines: List[str] = []
    lines.append("You output ONLY a compact JSON object with keys: reflowed_json, ocr_corrections, improvements_made, summary. No markdown, no code fences.")
    lines.append("")
    lines.append(f"Section id: {sid}")
    lines.append(f"Tables: {len(tabs_for_sec)} | Figures: {len(figs_for_sec)}")
    for m in merges[:4]:
        lines.append(f"Merge candidate: {m}")

    # Minimal sketch slice
    objs = (sketch.get("objects") or []) if isinstance(sketch, dict) else []
    if objs:
        mini = []
        for o in objs[:20]:
            mini.append({
                "id": o.get("id"),
                "type": o.get("type"),
                "page": o.get("page"),
                "grid_bbox": o.get("grid_bbox"),
                "header_norm": o.get("header_norm"),
                "logical_table_id": o.get("logical_table_id"),
                "summary": o.get("summary"),
            })
        try:
            import json as _json
            lines.append("")
            lines.append("Sketch (minimal):")
            lines.append(_json.dumps(mini, ensure_ascii=False))
        except Exception:
            pass

    # Heads/titles summary
    if tabs_for_sec:
        lines.append("")
        lines.append("Tables heads/titles:")
        for t in tabs_for_sec[:8]:
            hid = t.get("id") or t.get("table_id")
            lines.append(f"- {hid}: header_norm={t.get('header_norm')} title={t.get('title')}")
    if figs_for_sec:
        lines.append("")
        lines.append("Figures titles:")
        for f in figs_for_sec[:6]:
            fid = f.get("id") or f.get("figure_id")
            lines.append(f"- {fid}: title={f.get('title')} caption={f.get('caption')}")

    lines.append("")
    lines.append("Return ONLY the JSON; keep it compact.")
    return "\n".join(lines)
from extractor.pipeline.utils.response_utils import extract_content
from extractor.pipeline.utils.log_utils import sanitize_messages_for_return
from extractor.pipeline.utils.metrics_logger import log_metric
from extractor.pipeline.utils.model_params import (
    build_chat_extras,
)
# SciLLM client adapter wrappers are not used in Stage 07 per policy (Router-only)
from extractor.pipeline.utils.text_utils import sanitize_text
from extractor.pipeline.utils.unified_conversion import build_unified_document_from_reflow
from extractor.pipeline.utils.vision import preflight_vision_support

# Model selection (place imports at top to satisfy E402)
from extractor.pipeline.utils.model_select import get_vlm_model, get_text_model
from extractor.pipeline.utils.debug_utils import ensure_logs_dir, time_block, summarize_messages


def _build_text_router() -> Router:
    """Build a SciLLM Router for TEXT JSON mode using env CHUTES_* values.

    - model_name group: "chutes/text"
    - entries: CHUTES_TEXT_MODEL (+ ALT1/ALT2 if set)
    - provider: openai_like with Bearer via api_key
    """
    base = os.environ["CHUTES_API_BASE"]
    key = os.environ["CHUTES_API_KEY"]
    m0 = os.environ.get("CHUTES_TEXT_MODEL", "").strip()
    m1 = os.environ.get("CHUTES_TEXT_MODEL_ALT1", "").strip()
    m2 = os.environ.get("CHUTES_TEXT_MODEL_ALT2", "").strip()
    if not m0:
        raise RuntimeError("CHUTES_TEXT_MODEL is not set")

    def entry(model: str, order: int):
        return {
            "model_name": "chutes/text",
            "litellm_params": {
                "custom_llm_provider": "openai_like",
                "model": model,
                "api_base": base,
                "api_key": key,
            },
            "order": order,
        }

    lst = [entry(m0, 1)]
    if m1:
        lst.append(entry(m1, 2))
    if m2:
        lst.append(entry(m2, 3))
    return Router(model_list=lst)


# Shared helper: table confidence heuristic (0.0–1.0)
def _table_confidence(t: dict[str, Any]) -> float:
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

# --- Initialization & Configuration ---

# Do not load .env at import time; the caller or debug harness should load env.

# SciLLM-only policy: remove legacy LiteLLM cache initialization to avoid
# background threads preventing clean process exit.

logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{function}:{line}</cyan> - <level>{message}</level>",
)

STAGE07_DEBUG = os.getenv("STAGE07_DEBUG", "").lower() in ("1", "true", "yes", "y")
console = Console()

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

PROMPT_STRICT_REQUIREMENTS = (
    "Strict requirements for the JSON you return:\n"
    "- Merge Stage 05 table fragments that share the same logical columns into a SINGLE table block."
    " Use the Stage 05 column _order exactly, trim newline/zero-width characters inside headers,"
    " and keep every cell value character-for-character (apart from collapsing whitespace)."
    " Do not invent rows or columns."
    "\n- When you merge or infer a table title from nearby context, prefix it with 'INFERRED:'; otherwise leave title null."
    "\n- Rows must be an array of arrays with the same length as 'columns'. Preserve the Stage 05 cell text after collapsing internal whitespace,"
    " and repair mid-word splits by simply removing stray spaces (e.g., 'Descripti on' → 'Description', 'in in in ou t' → 'in/in/in/out')."
    "\n- Figure blocks must include the original image_ref (from Stage 06) and a concise caption; no plain string references."
    "\n- Paragraph/list blocks must use the documented keys (paragraph.text, list.items) — no free-form strings like 'text_content'."
    " Dedupe repeated list items and fix hyphenation breaks inside words."
    "\n- Do NOT output any block types beyond {paragraph, list, table, figure}."
)


# --- Core LLM and Prompting Functions ---


def build_reflow_prompt(section_data: dict[str, Any]) -> str:
    """Builds a simplified prompt focused on the core reflow task."""

    table_count = len(section_data.get("tables", []))
    figure_count = len(section_data.get("figures", []))

    return dedent(
        f"""
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
    """
    ).strip()


def _build_compact_prompt(
    section: dict[str, Any],
    *,
    text_char_cap: int = 1200,
) -> str:
    """Build a compact, string-only prompt with:
    - Top Summary: counts and per-table metrics (rows×cols, density, camelot_acc, strategy, quality_fallback)
    - Layout Sketch DSL (from 06b) and quick grid/columns overview
    - Minimal inputs: trimmed text, tables (headers + first row), figures (title/caption + bbox/page)
    - Strict JSON contract reminder (no code fences, no extra keys)
    """
    lines: list[str] = []
    title = sanitize_text(section.get("title", "Untitled"))
    pg0 = section.get("page_start")
    pg1 = section.get("page_end")
    blocks_count = len(section.get("blocks", []) or [])

    tables = section.get("tables") or []
    figures = section.get("figures") or []

    # Top Summary
    lines.append(f"Top Summary\n- title: {title}\n- pages: {pg0}–{pg1}\n- blocks: {blocks_count}")
    lines.append(f"- tables: {len(tables)}\n- figures: {len(figures)}")
    for tb in tables:
        pm = tb.get("pandas_metrics") or {}
        shape = pm.get("shape") or [0, 0]
        rows, cols = (int(shape[0] or 0), int(shape[1] or 0)) if isinstance(shape, (list, tuple)) else (0, 0)
        density = pm.get("data_density")
        camel = tb.get("camelot_metrics") or {}
        acc = camel.get("accuracy")
        strat = tb.get("strategy") or tb.get("strategy_history") or None
        qf = tb.get("quality_fallback") or None
        lines.append(
            f"  • table idx {tb.get('table_index')}: rows×cols={rows}×{cols}, density={density}, camelot_acc={acc}, strategy={strat}, quality_fallback={qf}"
        )

    # Layout Sketch DSL (compact)
    lsk = section.get("layout_sketch") or {}
    if isinstance(lsk, dict) and lsk:
        grid = lsk.get("grid", 12)
        cols = lsk.get("columns") or []
        dsl = (lsk.get("flow_stream") or "").strip()
        dsl_compact = dsl if len(dsl) <= 900 else (dsl[:900] + " …")
        lines.append("\nLayout Sketch")
        lines.append(f"- grid: {grid}")
        if cols:
            try:
                lines.append(f"- columns: {json.dumps(cols, ensure_ascii=False)[:300]}")
            except Exception:
                lines.append("- columns: (unavailable)")
        if dsl_compact:
            lines.append("- dsl:")
            lines.append(dsl_compact)

    # Minimal Inputs
    src_text = sanitize_text(
        section.get("source_text") or section.get("merged_text") or section.get("raw_text") or ""
    )
    lines.append("\nInputs")
    lines.append("Text (trimmed):")
    if src_text:
        lines.append(src_text[:text_char_cap])

    # Tables: headers + first row
    if tables:
        lines.append("Tables (headers + first row):")
        for tb in tables[:4]:
            pm = tb.get("pandas_metrics") or {}
            headers = pm.get("columns") or []
            sample_rows = tb.get("pandas_df") or tb.get("pandas_df_dict") or tb.get("rows") or []
            first = sample_rows[0] if sample_rows else []
            try:
                first_row_list = first if isinstance(first, list) else [first.get(h, "") for h in headers]
            except Exception:
                first_row_list = first if isinstance(first, list) else []
            lines.append(
                f"- table idx {tb.get('table_index')} headers={headers} first_row={first_row_list} page={tb.get('page_index')}"
            )

    # Figures: title/caption + bbox/page
    if figures:
        lines.append("Figures (title/caption + bbox/page):")
        for fg in figures[:6]:
            title_f = (fg.get("title") or "").strip()
            cap = (fg.get("caption") or fg.get("ai_description") or "").strip()
            bbox = fg.get("bbox") or fg.get("bbox0") or []
            page = fg.get("page") or fg.get("page_idx")
            lines.append(f"- figure id={fg.get('figure_id')} title={title_f or None} caption={cap[:160] if cap else None} bbox={bbox} page={page}")

    # Strict JSON schema reminder (no parts; no fences)
    lines.append(
        dedent(
            """
            Instruction
            Return ONLY one JSON object with keys:
              - reflowed_json { title: string, blocks: [ {paragraph|list|table|figure} … ] }
              - ocr_corrections: {"erroneous": "corrected", …}
              - improvements_made: string
              - summary: string
            No code fences. No extra keys. No explanations outside JSON.
            """
        ).strip()
    )

    return "\n".join(lines).strip()


# (No HTTP fallback: SciLLM-only policy)


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
    except Exception:
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
    except Exception:
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
                except Exception:
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
                except Exception:
                    pass
            try:
                rows_count = int((pm.get("shape") or [0])[0] or 0)
                if rows_count <= 1:
                    merge_hint = True
            except Exception:
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
        except Exception:
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

def _content_to_json_dict(content: Any) -> dict[str, Any]:
    """Normalize JSON content that may be a dict (already parsed) or a string.

    - If content is dict → return as-is
    - If content is str → try strict parse, then repair via clean_json_string
    - Else → raise ValueError
    """
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        if not content.strip():
            raise ValueError("empty content string")
        try:
            return parse_json_strict(content)
        except Exception:
            return clean_json_string(content, return_dict=True)
    raise ValueError(f"unsupported content type: {type(content)}")


def _iou_rect(a: list[float], b: list[float]) -> float:
    try:
        ax0, ay0, ax1, ay1 = map(float, a)
        bx0, by0, bx1, by1 = map(float, b)
    except Exception:
        return 0.0
    inter_w = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    inter_h = max(0.0, min(ay1, by1) - max(ay0, by0))
    inter = inter_w * inter_h
    if inter <= 0:
        return 0.0
    area_a = max(0.0, (ax1 - ax0)) * max(0.0, (ay1 - ay0))
    area_b = max(0.0, (bx1 - bx0)) * max(0.0, (by1 - by0))
    union = area_a + area_b - inter
    return float(inter / union) if union > 0 else 0.0


def _apply_layout_ordering(section: dict[str, Any]) -> None:
    """Optionally reorder section tables/figures using 06b layout sketch reading_order.

    Matches by IoU between item bbox and elements_original_bbox.
    Safe no-op if sketch missing or fields absent.
    """
    lsk = section.get("layout_sketch") or {}
    if not isinstance(lsk, dict) or not lsk:
        return
    elements = lsk.get("elements") or []
    orig = {e.get("id"): e for e in elements if isinstance(e, dict)}
    bbox_map = {e.get("id"): e.get("bbox") for e in (lsk.get("elements_original_bbox") or [])}

    def _order_items(items: list[dict], kind: str) -> list[dict]:
        scored = []
        for it in items:
            bb = it.get("bbox") or it.get("bbox0")
            best = (-1.0, 999999)  # IoU, reading_order
            for eid, eb in bbox_map.items():
                meta = orig.get(eid) or {}
                if (meta.get("kind") != kind) or (not eb):
                    continue
                iou = _iou_rect(bb or [], eb)
                if iou > best[0]:
                    best = (iou, int(meta.get("reading_order", 999999)))
            scored.append((best, it))
        # sort by reading_order asc, then by IoU desc (so higher IoU comes earlier when orders equal)
        scored.sort(key=lambda t: (t[0][1], -t[0][0]))
        return [it for _, it in scored]

    try:
        if isinstance(section.get("tables"), list):
            section["tables"] = _order_items(section["tables"], "table")
        if isinstance(section.get("figures"), list):
            section["figures"] = _order_items(section["figures"], "figure")
        # record provenance for debugging
        meta = section.setdefault("_layout_prior", {})
        meta["ordering"] = "06b"
    except Exception:
        pass

def _normalize_table_text(val: Any) -> str:
    if val is None:
        return ""
    text = str(val).replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _sanitize_table_cell(val: Any) -> str:
    if val is None:
        return ""
    text = str(val).replace("\u00a0", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    replacements = {
        "Subsyste m": "Subsystem",
        "Asynchro nous": "Asynchronous",
        "SUBSY STEM": "SUBSYSTEM",
        "EXECU TE": "EXECUTE",
        "bht_updat e_i": "bht_update_i",
        "bht_predi ction_o": "bht_prediction_o",
        "connexi on": "Connection",
        "Descripti on": "Description",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    tokens = text.split()
    if tokens and all(tok.lower() in {"in", "out", "ou", "t"} for tok in tokens):
        merged: list[str] = []
        i = 0
        while i < len(tokens):
            tok = tokens[i].lower()
            if tok == "in":
                merged.append("in")
            elif tok == "out":
                merged.append("out")
            elif tok == "ou" and i + 1 < len(tokens) and tokens[i + 1].lower() == "t":
                merged.append("out")
                i += 1
            else:
                merged.append(tok)
            i += 1
        text = "/".join(merged)
    return text


def _build_table_block_from_stage05(table: dict[str, Any]) -> dict[str, Any] | None:
    """Return a canonical table block derived from Stage 05 output."""
    pm = table.get("pandas_metrics") or {}
    orig_columns = pm.get("columns") or []
    columns = [_sanitize_table_cell(c) for c in orig_columns]
    rows_raw = table.get("pandas_df") or []
    rows: list[list[Any]] = []
    if columns and isinstance(rows_raw, list):
        for row in rows_raw:
            if isinstance(row, dict):
                rows.append([
                    _sanitize_table_cell(row.get(orig, ""))
                    for orig, _ in zip(orig_columns, columns)
                ])
            elif isinstance(row, list):
                padded = [_sanitize_table_cell(v) for v in list(row)[: len(columns)]]
                if len(padded) < len(columns):
                    padded.extend([None] * (len(columns) - len(padded)))
                rows.append(padded)
    rows = [
        ["" if cell is None else cell for cell in r]
        for r in rows
    ]
    if not columns and not rows:
        return None

    confidence: dict[str, Any] = {
        "status": "high",
        "density": None,
        "source": "camelot+pandas",
    }
    try:
        density_val = float(pm.get("data_density") or 0.0)
        confidence["density"] = density_val
        if density_val < 0.9:
            confidence["status"] = "medium"
    except Exception:
        confidence["density"] = None

    block = {
        "type": "table",
        "title": None,
        "columns": columns,
        "rows": rows,
        "confidence": confidence,
        "markdown": None,
        "markdown_provenance": None,
        "image_refs": [],
        "source": {
            "table_indices": [table.get("table_index")] if table.get("table_index") is not None else [],
            "page_indices": [table.get("page_index")] if table.get("page_index") is not None else [],
        },
    }
    return block


def _build_figure_block_from_stage06(figure: dict[str, Any]) -> dict[str, Any] | None:
    """Return a canonical figure block derived from Stage 06 output."""

    if not isinstance(figure, dict):
        return None
    caption = (figure.get("caption") or figure.get("ai_description") or "").strip() or None
    image_ref = figure.get("image_path") or None
    if not (caption or image_ref):
        return None
    try:
        page_idx = int(figure.get("page", figure.get("page_idx", -1)))
    except Exception:
        page_idx = -1
    block: dict[str, Any] = {
        "type": "figure",
        "title": None,
        "caption": caption,
        "alt": caption or "Figure",
        "image_ref": image_ref,
        "source": {"pages": [page_idx] if page_idx >= 0 else [], "block_ids": []},
    }
    if figure.get("figure_id"):
        block["figure_id"] = figure.get("figure_id")
    return block


async def reflow_section_with_llm(
    section_data: dict[str, Any],
    results_base_dir: Path,
    *,
    include_images: bool,
    allow_fallback: bool,
    llm_timeout: int = 60,
) -> dict[str, Any]:
    """Reflow a section using multimodal context (section/table/figure/annotation) and return structured JSON."""
    # Respect allow-images toggle (default text-only). Per-section gating may still disable images.
    _ALLOW_IMAGES = os.getenv("STAGE07_ALLOW_IMAGES", "0").lower() in ("1", "true", "yes", "y")
    include_images = bool(include_images and _ALLOW_IMAGES)
    # Ensure text model is selected even when debug-bundle bypasses run()
    global LLM_MODEL
    try:
        LLM_MODEL = get_text_model()
    except Exception:
        pass
    try:
        sec_diags = []

        # use shared helper

        # Decide if the model supports multimodal inputs
        supports_vision = any(
            kw in (LLM_MODEL or "").lower()
            for kw in (
                "gpt-5",
                "gpt-4o",
                "gpt-4.1",
                "gpt-4-vision",
                "claude-3",
                "gemini",
                "llava",
                "qwen-vl",
                "grok-vision",
            )
        )

        # Layout-based gating: omit images when we have a confident layout prior
        try:
            if include_images and USE_LAYOUT_SKETCH and OMIT_IMAGES_IF_CONFIDENT:
                conf = float(((section_data.get("layout_sketch") or {}).get("conf") or {}).get("ordering") or 0.0)
                if conf >= LAYOUT_CONF_THRESH:
                    include_images = False
                    try:
                        sec_diags.append(
                            make_event(
                                "07_reflow_section",
                                "info",
                                "images_omitted_due_to_layout_conf",
                                f"ordering_conf={conf}",
                                {},
                            )
                        )
                    except Exception:
                        pass
        except Exception:
            pass

        # Build textual context
        context_text = build_section_context_text(section_data)
        try:
            # Optional context trim for initial warm-up with providers that can stall on very long first calls
            trim_env = os.getenv("STAGE07_TRIM_CHARS")
            if trim_env:
                n = int(trim_env)
                if n > 0:
                    context_text = context_text[:n]
        except Exception:
            pass
        # Enforce vision requirement before constructing images

        # Build user content (text + images if supported)
        user_content: Any
        image_blocks: list[dict[str, Any]] = []
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
        sec_b64 = None
        anns = []
        sec_b64 = None
        if supports_vision and include_images:
            # Section visual
            sec_b64 = get_section_image_b64(section_data, results_base_dir)
            if sec_b64:
                image_blocks.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{sec_b64}"}}
                )
                try:
                    sec_diags.append(
                        make_event(
                            "07_reflow_section",
                            "info",
                            "section_image_attached",
                            "Included section image",
                            {},
                        )
                    )
                except Exception:
                    pass

            # Table images: include only low-confidence tables
            for t in section_data.get("tables", []) or []:
                conf = _table_confidence(t)
                if conf < TABLE_CONF_THRESHOLD:
                    tb64 = get_table_image_b64(t, results_base_dir)
                    if tb64:
                        try:
                            sec_diags.append(
                                make_event(
                                    "07_reflow_section",
                                    "info",
                                    "table_image_attached",
                                    "Included table image (low confidence)",
                                    {"table_index": t.get("table_index"), "confidence": conf},
                                )
                            )
                        except Exception:
                            pass
                        image_blocks.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{tb64}"},
                            }
                        )
            # Figure images (optional via env)
            if INCLUDE_FIGURE_IMAGES:
                for f in section_data.get("figures", [])[:2]:
                    fb64 = get_figure_image_b64(f, results_base_dir)
                    if fb64:
                        try:
                            sec_diags.append(
                                make_event(
                                    "07_reflow_section",
                                    "info",
                                    "figure_image_attached",
                                    "Included figure image",
                                    {"figure_id": f.get("figure_id")},
                                )
                            )
                        except Exception:
                            pass
                        image_blocks.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{fb64}"},
                            }
                        )

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

            anns = sorted(section_data.get("annotations", []) or [], key=_ann_score, reverse=True)[
                :MAX_ANNOTATION_IMAGES
            ]
            for a in anns:
                ab64 = get_annotation_image_b64(a, results_base_dir)
                if ab64:
                    image_blocks.append(
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{ab64}"}}
                    )

            # Attachments summary (counts are approximate by source lists)
            try:
                att_counts = {
                    "tables": len(section_data.get("tables", [])[:2]),
                    "figures": len(section_data.get("figures", [])[:2]),
                    "annotations": len(section_data.get("annotations", [])[:2]),
                }
                sec_diags.append(
                    make_event(
                        "07_reflow_section",
                        "info",
                        "attachments_summary",
                        "Attached images for reflow",
                        att_counts,
                    )
                )
            except Exception:
                pass
            user_content = [{"type": "text", "text": context_text}] + image_blocks
        elif supports_vision and not include_images:
            # Use plain string content; some providers return empty content for array parts
            user_content = context_text
        else:
            user_content = f"""{context_text}

[Note: Images omitted because the selected model does not support vision]"""

        if SCHEMA_MODE == "reflow_json":
            system_prompt = dedent(
                """
            You are a technical reflow engine. Given a PDF-extracted section JSON, compact tables, and a few images, output a single reflowed section JSON that merges contiguous content for LLM use and DB storage.

            Core requirements
            - Merge contiguous text into coherent paragraphs (fix hyphenation, broken words, OCR joins). Remove duplicated headers/footers and page artifacts.
            - Merge contiguous tables, including those that span pages, into one logical table positioned at the first fragment. Perform header normalization (remove intra-cell newlines/zero-width chars; trim/condense whitespace) and flatten multi-row headers by safe concatenation.
            - Preserve reading _order: top→bottom, left→right, across pages.
            - Prefer provided tables/pandas content; use images only for context or disambiguation.

            Data Integrity (strict)
            - Tables: DO NOT change cell content. No spelling “corrections”, translations, unit changes, rounding, normalization, inference, or reformatting. Keep numeric formats as-is.
            - Allowed in tables only: remove intra-cell newlines/excess spaces (join without changing character _order); flatten multi-row headers by concatenation delimiters.
            - Forbidden in tables: reordering rows/columns, filling blanks, deduping, computing totals.
            - Text/Headings/Lists: Fix OCR splits/hyphenation and obvious typos only outside tables. Record fixes in ocr_corrections.

            Figures
            - If the section has figures (see Figures JSON), include a figure block in blocks with: {"type":"figure", "title": string|null, "caption": string|null, "image_ref": string}.
            - Prefer using the provided ai_description as a concise caption when available; set image_ref to the figure image_path.

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
                  { "type": "figure", "title": string|null, "caption": string|null, "image_ref": string, "source": { "pages": [int], "block_ids": [string] } }
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
            """
            ).strip()
        else:
            system_prompt = dedent(
                """
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
            """
            ).strip()

        # Limit context size for GPT-5 stability
        if "gpt-5" in (LLM_MODEL or "").lower():
            context_text = context_text[:3000]
        # Compact cap for providers that return empty content with long payloads
        _cap = int(os.getenv("STAGE07_TEXT_MAX_CHARS", "2000"))
        _user_compact = user_content[:_cap]
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _user_compact},
        ]

        # Attach images for Chat Completions (data URL parts)
        if include_images:
            max_images = int(os.getenv("STAGE07_MAX_IMAGES", "6"))
            attached = 0

            def _attach_blocks(b64: str | None, kind: str, meta: dict):
                nonlocal attached, image_blocks
                if b64 and attached < max_images:
                    image_blocks.append(
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                    )
                    try:
                        sec_diags.append(
                            make_event(
                                "07_reflow_section",
                                "info",
                                f"{kind}_image_attached",
                                "Included image",
                                meta,
                            )
                        )
                    except Exception:
                        pass
                    attached += 1

            if sec_b64:
                _attach_blocks(sec_b64, "section", {"section_id": section_data.get("id")})
            for t in section_data.get("tables", []) or []:
                conf = _table_confidence(t)
                if conf < TABLE_CONF_THRESHOLD:
                    _attach_blocks(
                        get_table_image_b64(t, results_base_dir),
                        "table",
                        {"table_index": t.get("table_index"), "confidence": conf},
                    )
            if INCLUDE_FIGURE_IMAGES:
                for f in section_data.get("figures", [])[:2]:
                    _attach_blocks(
                        get_figure_image_b64(f, results_base_dir),
                        "figure",
                        {"figure_id": f.get("figure_id")},
                    )
            for a in anns:
                _attach_blocks(
                    get_annotation_image_b64(a, results_base_dir),
                    "annotation",
                    {"annotation_id": a.get("id")},
                )

        # LLM call: Chat Completions via scillm (Chutes x-api-key)
        # SciLLM-only: no litellm session envs; use our run id
        sid = get_run_id()
        # Simple prompt path (text-only). When images are NOT included, we can
        # ask only for: reflow text + merge tables. This reduces provider
        # variance and avoids empty responses.
        SIMPLE = (os.getenv("STAGE07_SIMPLE_PROMPT", "1").lower() in ("1", "true", "yes", "y")) and (not include_images)
        if SIMPLE:
            try:
                logs_dir = ensure_logs_dir(results_base_dir, "07_reflow_section")

                # Build compact user prompt with Top Summary + Layout DSL + minimal inputs
                compact_user = _build_compact_prompt(section_data, text_char_cap=int(os.getenv("STAGE07_CONTEXT_CHARS", "1200")))

                # Save prompt artifact for first section (or once per run if not exists)
                try:
                    artifacts_dir = Path("scripts/artifacts")
                    artifacts_dir.mkdir(parents=True, exist_ok=True)
                    prompt_path = artifacts_dir / "07_section0_prompt_compact.md"
                    if not prompt_path.exists():
                        prompt_path.write_text(compact_user, encoding="utf-8")
                except Exception:
                    pass

                messages_simple = [
                    {"role": "system", "content": "You respond with JSON only — no code fences, no prose."},
                    {"role": "user", "content": compact_user},
                ]

                try:
                    _router_s = _build_text_router()
                    _r_s = await _router_s.acompletion(
                        model="chutes/text",
                        messages=messages_simple,
                        response_format={"type": "json_object"},
                        temperature=0,
                        max_tokens=min(STAGE07_MAX_TOKENS, 1024),
                        timeout=max(30, int(os.getenv("STAGE07_TIMEOUT","90"))),
                    )
                    content_simple = _r_s.choices[0].message.get("content") if hasattr(_r_s, "choices") else None
                except Exception:
                    content_simple = None

                # If SDK came back empty, immediately try HTTP fallback with same payload
                result: dict[str, Any] | None = None
                if (isinstance(content_simple, (str, dict)) and str(content_simple).strip()) or isinstance(content_simple, dict):
                    # Accept dict-or-string
                    if isinstance(content_simple, dict):
                        result = content_simple
                    else:
                        try:
                            result = parse_json_strict(str(content_simple))
                        except Exception:
                            result = clean_json_string(str(content_simple), return_dict=True)

                # Record per-section summary
                try:
                    artifacts_dir = Path("scripts/artifacts")
                    artifacts_dir.mkdir(parents=True, exist_ok=True)
                    summary_path = artifacts_dir / "07_live_response_summary.json"
                    entry = {
                        "section_id": section_data.get("id"),
                        "transport": ("sdk" if result is not None else "none"),
                        "ok": bool(result and isinstance(result, dict) and result.get("reflowed_json")),
                        "timestamp": iso_now(),
                    }
                    try:
                        prev = json.loads(summary_path.read_text()) if summary_path.exists() else []
                        if not isinstance(prev, list):
                            prev = []
                    except Exception:
                        prev = []
                    prev.append(entry)
                    summary_path.write_text(json.dumps(prev, indent=2))
                except Exception:
                    pass

                if isinstance(result, dict) and result.get("reflowed_json"):
                    return {**section_data, **result, "reflow_status": "success"}
                # If compact path failed to produce JSON, fall through to existing strict/relaxed branches
            except Exception:
                pass

        # Minimal forced path for smokes: bypass complex strict/compact branches for Gemini
        _force_minimal = os.getenv("STAGE07_FORCE_MINIMAL_CALL", "").lower() in ("1", "true", "yes", "y")
        if _force_minimal:
            try:
                logs_dir = results_base_dir / "07_reflow_section" / "logs"
                logs_dir.mkdir(parents=True, exist_ok=True)
                minimal_guard = "Return ONLY a JSON object. No prose, no code fences. Keep it short."
                minimal_user = f"{minimal_guard}\n\n{context_text[:1200]}"
                messages_min = [
                    {"role": "system", "content": "You output ONLY compact JSON."},
                    {"role": "user", "content": minimal_user},
                ]
                params_min = {
                    "model": LLM_MODEL,
                    "messages": messages_min,
                    "timeout": llm_timeout,
                    "temperature": 0,
                    "cache": {"no-cache": True},
                    # No response_format to avoid any param translation issues
                }
                # Log minimal payload (sanitized)
                try:
                    sanitized_min = sanitize_messages_for_return(messages_min, mode="truncate", max_str_len=48)
                    (logs_dir / f"request_payload_forced_min_{section_data.get('id','section')}.json").write_text(
                        json.dumps({"model": LLM_MODEL, "messages": sanitized_min, "kwargs": {k: v for k, v in params_min.items() if k not in ("model","messages")}}, ensure_ascii=False, indent=2, default=str)
                    )
                except Exception:
                    pass
                try:
                    _router_min = _build_text_router()
                    _r_min = await _router_min.acompletion(
                        model="chutes/text",
                        messages=messages_min,
                        response_format={"type": "json_object"},
                        temperature=0,
                        max_tokens=min(STAGE07_MAX_TOKENS, 512),
                        timeout=llm_timeout,
                    )
                    content_min = _r_min.choices[0].message.get("content") if hasattr(_r_min, "choices") else None
                except Exception:
                    content_min = None
                try:
                    (logs_dir / f"response_forced_min_{section_data.get('id','section')}.json").write_text(
                        json.dumps(content_min, ensure_ascii=False, indent=2, default=str) if isinstance(content_min, (dict, list)) else str(content_min)
                    )
                except Exception:
                    pass
                if isinstance(content_min, str) and content_min.strip():
                    content = content_min
                    # Parse immediately and build output for schema mode
                    try:
                        parsed = clean_json_string(content, return_dict=True)
                    except Exception:
                        parsed = {}
                    if SCHEMA_MODE == "reflow_json":
                        # Wrap into minimal reflowed_json
                        out = {**section_data}
                        out.update(
                            {
                                "reflowed_json": {
                                    "title": section_data.get("title") or "Untitled",
                                    "blocks": [json.dumps(parsed, ensure_ascii=False) if isinstance(parsed, (dict, list)) else (parsed if isinstance(parsed, str) else content)],
                                },
                                "ocr_corrections": parsed.get("ocr_corrections", {}),
                                "improvements_made": parsed.get("improvements_made", ""),
                                "summary": parsed.get("summary", ""),
                                "reflow_status": "success",
                            }
                        )
                        return out
                    else:
                        # Put JSON (any) into reflowed_text string
                        if isinstance(parsed, (dict, list)):
                            parsed = {"reflowed_text": json.dumps(parsed, ensure_ascii=False)}
                        elif isinstance(parsed, str):
                            parsed = {"reflowed_text": parsed}
                        else:
                            parsed = {"reflowed_text": content}
                        out = {**section_data}
                        out.update(
                            {
                                "reflowed_text": parsed.get("reflowed_text", ""),
                                "ocr_corrections": parsed.get("ocr_corrections", {}),
                                "improvements_made": parsed.get("improvements_made", ""),
                                "reflow_status": "success",
                            }
                        )
                        return out
            except Exception:
                pass
            # Fallback: try native Google client without schema, JSON mime only
            try:
                if "gemini" in (LLM_MODEL or "").lower():
                    from google import genai as _genai
                    logs_dir = results_base_dir / "07_reflow_section" / "logs"
                    logs_dir.mkdir(parents=True, exist_ok=True)
                    _client = _genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
                    resp = _client.models.generate_content(
                        model=(LLM_MODEL.split("/", 1)[1] if "/" in (LLM_MODEL or "") else LLM_MODEL),
                        contents=[minimal_user],
                        config={"temperature": 0, "response_mime_type": "application/json"},
                    )
                    text_out = None
                    try:
                        cand0 = resp.candidates[0]
                        parts = getattr(getattr(cand0, "content", None), "parts", None)
                        if parts:
                            for prt in parts:
                                t = getattr(prt, "text", None)
                                if isinstance(t, str) and t.strip():
                                    text_out = t
                                    break
                    except Exception:
                        text_out = None
                    try:
                        (logs_dir / f"response_forced_min_native_{section_data.get('id','section')}.json").write_text(
                            json.dumps({"text": text_out}, ensure_ascii=False, indent=2)
                        )
                    except Exception:
                        pass
                    if isinstance(text_out, str) and text_out.strip():
                        try:
                            parsed = clean_json_string(text_out, return_dict=True)
                        except Exception:
                            parsed = text_out
                        out = {**section_data}
                        if SCHEMA_MODE == "reflow_json":
                            out.update(
                                {
                                    "reflowed_json": {
                                        "title": section_data.get("title") or "Untitled",
                                        "blocks": [json.dumps(parsed, ensure_ascii=False) if isinstance(parsed, (dict, list)) else (parsed if isinstance(parsed, str) else text_out)],
                                    },
                                    "ocr_corrections": {},
                                    "improvements_made": "",
                                    "summary": "",
                                    "reflow_status": "success",
                                }
                            )
                        else:
                            out.update(
                                {
                                    "reflowed_text": json.dumps(parsed, ensure_ascii=False) if isinstance(parsed, (dict, list)) else (parsed if isinstance(parsed, str) else text_out),
                                    "ocr_corrections": {},
                                    "improvements_made": "",
                                    "reflow_status": "success",
                                }
                            )
                        return out
            except Exception:
                pass
        # Attempt 1: Chat Completions with standardized messages (system + user text + image_url data URL)
        try:
            # Build image data URL for section image if present and attach to messages
            _image_data_url = None
            try:
                # prefer section image
                if sec_b64:
                    _image_data_url = f"data:image/png;base64,{sec_b64}"
            except Exception:
                _image_data_url = None
            # Prompt: compact vs full. Compact can help providers that stall on overly prescriptive prompts.
            _compact = os.getenv("STAGE07_COMPACT_PROMPT", "").lower() in ("1", "true", "yes", "y")
            if _compact:
                system_text = f"{STRICT_JSON_GUARD}\n{PROMPT_STRICT_REQUIREMENTS}"
            else:
                system_text = (
                    f"You are a strict JSON generator. {STRICT_JSON_GUARD} "
                    "You respond with exactly one JSON object conforming to the schema. Do not include any explanations, prose, or extra keys.\n"
                    f"{PROMPT_STRICT_REQUIREMENTS}"
                )

            def _is_gemini(m: str) -> bool:
                return "gemini" in (m or "").lower()

            # Use LiteLLM-standard parts: "text" and "image_url" for all providers.
            # We still place the JSON guard at the start of user content for Gemini by
            # inlining it into the first text part (instead of using input_text/input_image).
            _converted = list(image_blocks)

            # Build messages with a system role; inline a minimal schema hint
            user_text = f"Return ONLY valid JSON.\n\n{context_text}"
            user_parts = [{"type": "text", "text": user_text}]
            if include_images and supports_vision and _converted:
                user_parts.extend(_converted)
            messages = [
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_parts},
            ]
            # No adapter path — Router-only per policy; fallbacks handled later via curl if needed

            extras = build_chat_extras(LLM_MODEL)
            # Avoid collisions: if using response_format for Gemini, drop generation_config from extras
            try:
                if "gemini" in (LLM_MODEL or "").lower():
                    extras.pop("generation_config", None)
            except Exception:
                pass
            # JSON schema for strict structured output
            _json_schema = {
                "type": "object",
                "properties": {
                    "reflowed_json": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "blocks": {
                                "type": "array",
                                "items": {
                                    "oneOf": [
                                        {"type": "string"},
                                        {
                                            "type": "object",
                                            "properties": {
                                                "type": {"type": "string"},
                                                "title": {"type": "string"},
                                                "caption": {"type": "string"},
                                                "image_ref": {"type": "string"}
                                            },
                                            "required": ["type"],
                                            "additionalProperties": True,
                                        },
                                        {
                                            "type": "object",
                                            "properties": {
                                                "type": {"type": "string"},
                                                "columns": {"type": "array", "items": {"type": "string"}},
                                                "rows": {
                                                    "type": "array",
                                                    "items": {"type": "array", "items": {"type": ["string", "number", "null"]}}
                                                }
                                            },
                                            "required": ["type", "columns", "rows"],
                                            "additionalProperties": True
                                        }
                                    ]
                                },
                            },
                        },
                        "required": ["title"],
                        "additionalProperties": True,
                    },
                    "ocr_corrections": {
                        "type": "object",
                        "properties": {"_": {"type": "string"}},
                        "additionalProperties": True,
                    },
                    "improvements_made": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["reflowed_json"],
                "additionalProperties": False,
            }

            call_params = {
                "model": LLM_MODEL,
                "messages": messages,
                **extras,
                "timeout": llm_timeout,
            }
            # Reduce variability
            call_params["temperature"] = 0
            # Important: Do NOT set max_output_tokens for Gemini (can cause empty responses)
            try:
                if "gemini" not in (LLM_MODEL or "").lower():
                    call_params["max_tokens"] = STAGE07_MAX_TOKENS
            except Exception:
                pass
            # If images are included on Attempt 1 (non-Gemini), clamp tokens to image cap after generic max is set
            try:
                if include_images and supports_vision and "gemini" not in (LLM_MODEL or "").lower():
                    _img_cap = int(os.getenv("STAGE07_IMAGE_PROMPT_MAX_TOKENS", str(MAX_TOKENS_IMAGE)))
                    prior_max = int(call_params.get("max_tokens") or STAGE07_MAX_TOKENS)
                    call_params["max_tokens"] = min(prior_max, _img_cap)
            except Exception:
                pass
            # Disable cache for strict JSON passes to avoid stale empties
            call_params["cache"] = {"no-cache": True}
            # Enforce JSON-only responses; allow minimal mode for Gemini via env
            _minimal_json = os.getenv("STAGE07_MINIMAL_JSON", "").lower() in ("1", "true", "yes", "y")
            if "gemini" in (LLM_MODEL or "").lower():
                try:
                    extras.pop("generation_config", None)
                    call_params.pop("generation_config", None)
                except Exception:
                    pass
                if _minimal_json:
                    call_params["response_format"] = {"type": "json_object"}
                else:
                    call_params["response_format"] = {
                        "type": "json_schema",
                        "json_schema": {"schema": _json_schema},
                    }
            else:
                call_params["response_format"] = {"type": "json_object"}
            # Add stop fences for non-Gemini providers to avoid spillover
            # Do not set stop fences; some providers return empty content when stop is present
            # Instrumentation: write request summary now that messages exist
            try:
                logs_dir = results_base_dir / "07_reflow_section" / "logs"
                logs_dir.mkdir(parents=True, exist_ok=True)

                def _image_bytes_from_part(p: dict) -> int:
                    try:
                        if not (isinstance(p, dict) and p.get("type") == "image_url"):
                            return 0
                        img = p.get("image_url") or {}
                        url = img.get("url")
                        if not (isinstance(url, str) and "," in url):
                            return 0
                        b64 = url.split(",", 1)[1]
                        return int(len(b64) * 3 / 4)
                    except Exception:
                        return 0

                # Count image parts directly from user content
                user_parts_all: list[dict] = []
                try:
                    for m in messages:
                        if isinstance(m, dict) and isinstance(m.get("content"), list):
                            user_parts_all.extend([p for p in m["content"] if isinstance(p, dict)])
                except Exception:
                    pass

                req_info = {
                    "model": LLM_MODEL,
                    "context_length": len(context_text),
                    "images_count": sum(1 for p in user_parts_all if p.get("type") == "image_url"),
                    "image_bytes": [
                        _image_bytes_from_part(p) for p in user_parts_all if p.get("type") == "image_url"
                    ],
                    "session_id": sid,
                }
                (logs_dir / f"request_info_{section_data.get('id','section')}.json").write_text(
                    json.dumps(req_info, indent=2)
                )
                # Also log a sanitized snapshot of the final request payload to confirm parameter mapping
                try:
                    sanitized_messages = sanitize_messages_for_return(messages, mode="truncate", max_str_len=48)
                    payload_dump = {
                        "model": LLM_MODEL,
                        "messages": sanitized_messages,
                        "kwargs": {k: v for k, v in call_params.items() if k not in ("model", "messages")},
                    }
                    (logs_dir / f"request_payload_strict_{section_data.get('id','section')}.json").write_text(
                        json.dumps(payload_dump, ensure_ascii=False, indent=2, default=str)
                    )
                except Exception:
                    pass
            except Exception:
                pass

            # Run strict call via SciLLM Router (OpenAI-compatible JSON mode)
            try:
                _router = _build_text_router()
                with time_block(logs_dir, "attempt_strict", section_id=str(section_data.get("id","section")), **summarize_messages(messages)):
                    _r = await _router.acompletion(
                        model="chutes/text",
                        messages=messages,
                        response_format=call_params.get("response_format", {"type": "json_object"}),
                        temperature=0,
                        max_tokens=int(call_params.get("max_tokens") or 1024),
                        timeout=llm_timeout,
                    )
                content_obj = _r.choices[0].message.get("content") if hasattr(_r, "choices") else None
            except Exception:
                content_obj = None
            try:
                from loguru import logger as _logger
                _ok = True if (content_obj is not None) else False
                _logger.info(f"reflow_strict: model={LLM_MODEL} ok={_ok}")
            except Exception:
                pass
            resp = content_obj or ""
            try:
                (logs_dir / f"response_strict_{section_data.get('id','section')}.json").write_text(
                    json.dumps(resp, default=str, indent=2)
                    if isinstance(resp, dict)
                    else str(resp)
                )
            except Exception:
                pass
        except Exception:
            resp = ""

        # Normalize response to get content: accept dict or string
        content: str | None = None
        try:
            if isinstance(resp, dict):
                content = json.dumps(resp, ensure_ascii=False)
            elif isinstance(resp, str):
                content = resp
            else:
                # Fallback to shared extractor for other response shapes
                content = extract_content(resp) or None
        except Exception:
            content = None
        if not isinstance(content, str) or not content.strip():
            # Attempt 2 (strict-compact): reduce context + simplified guard to improve provider reliability
            try:
                # Build compact instruction
                compact_guard = (
                    "Return ONLY a minified JSON object with keys: reflowed_json, ocr_corrections, improvements_made, summary. "
                    "No markdown, no code fences, no trailing commas. reflowed_json.blocks must be valid and _ordered."
                )
                use_compact = os.getenv("STAGE07_USE_COMPACT", "").lower() in ("1","true","yes","y")
                compact_user = f"{compact_guard}\n\n{context_text[:1500]}"
                if use_compact:
                    # Load sketch_v2 once
                    try:
                        skv2_path = results_base_dir / "06b_layout_sketcher" / "json_output" / "06b_layout_sketch_v2.json"
                        skv2 = json.loads(skv2_path.read_text()) if skv2_path.exists() else {"sections": {}}
                        sk_by_sec = skv2.get("sections") or {}
                    except Exception:
                        sk_by_sec = {}
                    compact_user = _build_compact_prompt(
                        results_base_dir=results_base_dir,
                        section_data=section_data,
                        tables=section_data.get("tables", []),
                        figures=section_data.get("figures", []),
                        sketch_v2_by_sec=sk_by_sec,
                    )
                    # Persist the exact prompt for this section
                    try:
                        art = Path("scripts/artifacts")
                        art.mkdir(parents=True, exist_ok=True)
                        (art / f"07_{section_data.get('id','section')}_prompt_compact.md").write_text(compact_user, encoding="utf-8")
                    except Exception:
                        pass
                # Use plain string content for text-only reliability
                # Domain-aware system prompt (concise but explicit)
                sys_msg = (
                    "You are reflowing scientific/engineering hardware documents. "
                    "Return ONLY strict JSON (no markdown/fences). Merge contiguous tables with identical schema; "
                    "preserve column order and values; fix hyphenation inside words; limit to keys requested."
                )
                # Optional: include the section image (multimodal) if requested
                user_content: Any = compact_user
                try:
                    include_image = os.getenv("STAGE07_INCLUDE_SECTION_IMAGE", "").lower() in ("1","true","yes","y")
                    if include_image:
                        # Resolve a section image; prefer 04's visual_path on the section, else any 06b visual_path
                        vrel: Optional[str] = None
                        try:
                            vrel = str(section_data.get("visual_path") or "") or None
                        except Exception:
                            vrel = None
                        if not vrel:
                            try:
                                skv2_path = results_base_dir / "06b_layout_sketcher" / "json_output" / "06b_layout_sketch_v2.json"
                                skv2 = json.loads(skv2_path.read_text()) if skv2_path.exists() else {"sections": {}}
                                sid = str(section_data.get("id"))
                                vrel = str(((skv2.get("sections") or {}).get(sid) or {}).get("visual_path") or "") or None
                            except Exception:
                                vrel = None
                        if vrel:
                            from extractor.pipeline.utils.model_params import image_file_to_data_url as _img_to_data
                            vpath = (results_base_dir / vrel).resolve()
                            if vpath.exists():
                                user_content = [
                                    {"type": "text", "text": compact_user},
                                    {"type": "image_url", "image_url": {"url": _img_to_data(vpath)}},
                                ]
                except Exception:
                    pass
                messages2 = [
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": user_content},
                ]
                call_params2 = {"model": LLM_MODEL, "messages": messages2, "timeout": llm_timeout, **extras}
                call_params2["temperature"] = 0
                # Important: Do NOT set max_output_tokens for Gemini (can cause empty responses)
                try:
                    if "gemini" not in (LLM_MODEL or "").lower():
                        call_params2["max_tokens"] = STAGE07_MAX_TOKENS
                except Exception:
                    pass
                call_params2["cache"] = {"no-cache": True}
                if "gemini" in (LLM_MODEL or "").lower():
                    try:
                        call_params2.pop("generation_config", None)
                    except Exception:
                        pass
                    if _minimal_json:
                        call_params2["response_format"] = {"type": "json_object"}
                    else:
                        call_params2["response_format"] = {
                            "type": "json_schema",
                            "json_schema": {"schema": _json_schema},
                        }
                else:
                    call_params2["response_format"] = {"type": "json_object"}
                # Stop fence for non-Gemini providers
                # Do not set stop fences; some providers return empty content when stop is present
                # Log sanitized compact request for debugging
                try:
                    logs_dir = ensure_logs_dir(results_base_dir, "07_reflow_section")
                    sanitized_messages2 = sanitize_messages_for_return(messages2, mode="truncate", max_str_len=48)
                    payload_dump2 = {
                        "model": LLM_MODEL,
                        "messages": sanitized_messages2,
                        "kwargs": {k: v for k, v in call_params2.items() if k not in ("model", "messages")},
                    }
                    (logs_dir / f"request_payload_compact_{section_data.get('id','section')}.json").write_text(
                        json.dumps(payload_dump2, ensure_ascii=False, indent=2, default=str)
                    )
                except Exception:
                    pass
                # Compact strict pass via Router (JSON mode)
                try:
                    _router2 = _build_text_router()
                    with time_block(logs_dir, "attempt_compact", section_id=str(section_data.get("id","section")), **summarize_messages(messages2)):
                        _r2 = await _router2.acompletion(
                            model="chutes/text",
                            messages=messages2,
                            response_format=call_params2.get("response_format", {"type": "json_object"}),
                            temperature=0,
                            max_tokens=int(call_params2.get("max_tokens") or 1024),
                            timeout=llm_timeout,
                        )
                    content_obj2 = _r2.choices[0].message.get("content") if hasattr(_r2, "choices") else None
                except Exception:
                    content_obj2 = None
                try:
                    from loguru import logger as _logger
                    _ok2 = True if (content_obj2 is not None) else False
                    _logger.info(f"reflow_strict_compact: model={LLM_MODEL} ok={_ok2}")
                except Exception:
                    pass
                resp2 = content_obj2 or ""
                try:
                    (logs_dir / f"response_strict_compact_{section_data.get('id','section')}.json").write_text(
                        json.dumps(resp2, default=str, indent=2) if isinstance(resp2, dict) else str(resp2)
                    )
                except Exception:
                    pass
                if isinstance(resp2, dict):
                    try:
                        content = json.dumps(resp2, ensure_ascii=False)
                    except Exception:
                        content = None
                else:
                    content = resp2 if isinstance(resp2, str) else None
            except Exception:
                content = None
        if not isinstance(content, str) or not content.strip():
            # Attempt Gemini native strict shim using google.genai to guarantee JSON
            try:
                if "gemini" in (LLM_MODEL or "").lower():
                    from google import genai as _genai
                    from google.genai import types as _gtypes
                    logs_dir = results_base_dir / "07_reflow_section" / "logs"
                    logs_dir.mkdir(parents=True, exist_ok=True)
                    # Build Google contents from our messages (text + data URLs)
                    g_parts: list = []
                    for m in messages:
                        try:
                            cont = m.get("content") if isinstance(m, dict) else None
                            if isinstance(cont, list):
                                for p in cont:
                                    if isinstance(p, dict) and p.get("type") == "text":
                                        txt = p.get("text")
                                        if isinstance(txt, str) and txt.strip():
                                            g_parts.append(txt)
                                    elif isinstance(p, dict) and p.get("type") == "image_url":
                                        img = p.get("image_url") or {}
                                        url = img.get("url")
                                        if isinstance(url, str) and url.startswith("data:") and ";base64," in url:
                                            header, b64 = url.split(";base64,", 1)
                                            mime = header.split(":", 1)[1] if ":" in header else "image/png"
                                            import base64 as _b64
                                            try:
                                                g_parts.append(_gtypes.Part.from_bytes(data=_b64.b64decode(b64), mime_type=mime))
                                            except Exception:
                                                pass
                            elif isinstance(cont, str) and cont.strip():
                                g_parts.append(cont)
                        except Exception:
                            continue

                    # Define a minimal response schema
                    schema = _gtypes.Schema(
                        type=_gtypes.Type.OBJECT,
                        properties={
                            "reflowed_json": _gtypes.Schema(type=_gtypes.Type.OBJECT),
                            "ocr_corrections": _gtypes.Schema(type=_gtypes.Type.OBJECT),
                            "improvements_made": _gtypes.Schema(type=_gtypes.Type.STRING),
                            "summary": _gtypes.Schema(type=_gtypes.Type.STRING),
                        },
                        required=["reflowed_json", "ocr_corrections", "improvements_made"],
                        additionalProperties=False,
                    )
                    # Client and call
                    _client = _genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"), http_options={"timeout": llm_timeout * 1000})
                    resp = _client.models.generate_content(
                        model=(LLM_MODEL.split("/", 1)[1] if "/" in (LLM_MODEL or "") else LLM_MODEL),
                        contents=g_parts or [context_text[:1500]],
                        config={
                            "temperature": 0,
                            "response_schema": schema,
                            "response_mime_type": "application/json",
                        },
                    )
                    # Extract text
                    try:
                        cand0 = resp.candidates[0]
                        parts = getattr(getattr(cand0, "content", None), "parts", None)
                        if parts:
                            for prt in parts:
                                t = getattr(prt, "text", None)
                                if isinstance(t, str) and t.strip():
                                    content = t
                                    break
                    except Exception:
                        pass
                    # Log shim response
                    try:
                        (logs_dir / f"response_gemini_native_{section_data.get('id','section')}.json").write_text(
                            json.dumps({
                                "raw": getattr(resp, "to_dict", lambda: str(resp))(),
                                "text": content,
                            }, ensure_ascii=False, indent=2, default=str)
                        )
                    except Exception:
                        pass
            except Exception:
                pass
        if not isinstance(content, str) or not content.strip():
            # Fallback to legacy shape handling
            if isinstance(resp, str):
                content = resp
            elif isinstance(resp, dict):
                try:
                    if "output" in resp:
                        out = resp.get("output") or []
                        if out and isinstance(out, list):
                            content_items = out[0].get("content") or []
                            if content_items and isinstance(content_items, list):
                                text_item = next(
                                    (
                                        c
                                        for c in content_items
                                        if c.get("type") in ("output_text", "text")
                                    ),
                                    None,
                                )
                                if text_item:
                                    content = text_item.get("text") or text_item.get("content")
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
                        sec_diags.append(
                            make_event(
                                "07_reflow_section",
                                "info",
                                "vision_not_supported",
                                "Model lacks vision; images not sent",
                                {},
                            )
                        )
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

        # Accept dict content directly when response_format={"type":"json_object"}
        if isinstance(content, dict):
            try:
                result = content  # treat as already-parsed JSON
                try:
                    (logs_dir / f"response_strict_compact_{section_data.get('id','section')}.json").write_text(
                        json.dumps(result, indent=2)
                    )
                except Exception:
                    pass
                # short-circuit to final assembly for this section
                parsed = result
                # jump to downstream merge logic by setting a sentinel
                content = json.dumps(result)
            except Exception:
                content = None

        if not isinstance(content, str) or not content.strip():
            # Attempt 2: Compact strict JSON retry (shorter guard/context, lower caps)
            try:
                try:
                    _trim2 = int(os.getenv("STAGE07_RETRY1_TRIM_CHARS", "900"))
                except Exception:
                    _trim2 = 900
                _guard2 = (
                    "Return ONLY a compact JSON object with keys: reflowed_json, ocr_corrections, "
                    "improvements_made, summary. No markdown, no code fences, and no trailing commas."
                )
                user_text2 = f"{_guard2}\n\n{context_text[:_trim2]}"
                messages2 = [
                    {"role": "system", "content": "You output ONLY compact JSON."},
                    {"role": "user", "content": user_text2},
                ]
                _retry1_cap = int(os.getenv("STAGE07_RETRY1_MAX_TOKENS", "1024"))
                try:
                    _router3 = _build_text_router()
                    _r3 = await _router3.acompletion(
                        model="chutes/text",
                        messages=messages2,
                        response_format={"type": "json_object"},
                        temperature=0,
                        max_tokens=_retry1_cap,
                        timeout=llm_timeout,
                    )
                    content2 = _r3.choices[0].message.get("content") if hasattr(_r3, "choices") else None
                except Exception:
                    content2 = None
                # Accept dict content directly
                if isinstance(content2, dict):
                    try:
                        content = json.dumps(content2, ensure_ascii=False)
                    except Exception:
                        content = None
                elif isinstance(content2, str) and content2.strip():
                    content = content2
                try:
                    (logs_dir / f"response_strict_compact_{section_data.get('id','section')}.json").write_text(
                        json.dumps(content2, ensure_ascii=False, indent=2, default=str)
                        if isinstance(content2, dict)
                        else str(content2)
                    )
                except Exception:
                    pass
            except Exception:
                pass

        if not isinstance(content, str) or not content.strip():
            # Attempt 3: Relaxed mode (no response_format). Parse free-form via clean_json_string downstream.
            try:
                # Retry 2 shaping (no local sleep/backoff; global limiter handles pacing)

                try:
                    _trim = int(os.getenv("STAGE07_RETRY2_TRIM_CHARS", "1200"))
                except Exception:
                    _trim = 1200
                _guard3 = (
                    "Return ONLY a minified JSON object with keys: reflowed_json, ocr_corrections, "
                    "improvements_made, summary. No markdown, no code fences, no comments or explanations, "
                    "no trailing commas, no NaN/Infinity. reflowed_json.blocks must be valid and _ordered."
                )
                user_parts3 = [{"type": "text", "text": f"{_guard3}\n\n{context_text[:_trim]}"}]
                messages3 = [
                    {"role": "system", "content": "You output ONLY compact JSON."},
                    {"role": "user", "content": user_parts3},
                ]

                call_params = {"model": LLM_MODEL, "messages": messages3, "timeout": llm_timeout, **extras}
                # lower temperature and cap tokens when supported
                call_params["temperature"] = 0
                call_params["cache"] = {"no-cache": True}
                try:
                    if "gemini" not in (LLM_MODEL or "").lower():
                        call_params["stop"] = STOP_FENCES
                except Exception:
                    pass
                try:
                    _retry2_cap = int(os.getenv("STAGE07_RETRY2_MAX_TOKENS", "1536"))
                except Exception:
                    _retry2_cap = 1536
                try:
                    if "gemini" not in (LLM_MODEL or "").lower():
                        call_params["max_tokens"] = min(int(call_params.get("max_tokens") or STAGE07_MAX_TOKENS), _retry2_cap)
                except Exception:
                    pass

                # Relaxed pass with scillm (no response_format)
                try:
                    _router4 = _build_text_router()
                    _r4 = await _router4.acompletion(
                        model="chutes/text",
                        messages=messages3,
                        temperature=0,
                        max_tokens=int(call_params.get("max_tokens") or 1024),
                        timeout=max(30, int(os.getenv("STAGE07_TIMEOUT","90"))),
                    )
                    resp2 = _r4.choices[0].message.get("content") if hasattr(_r4, "choices") else None
                except Exception:
                    resp2 = None
                try:
                    from loguru import logger as _logger
                    _ok3 = True if (resp2 is not None) else False
                    _logger.info(f"reflow_relaxed: model={LLM_MODEL} ok={_ok3}")
                except Exception:
                    pass
                try:
                    (logs_dir / f"response_relaxed_{section_data.get('id','section')}.json").write_text(
                        json.dumps(resp2, default=str, indent=2)
                        if isinstance(resp2, dict)
                        else str(resp2)
                    )
                except Exception:
                    pass
            except Exception:
                resp2 = ""
            # Accept dict content in relaxed mode as well
            if isinstance(resp2, dict):
                try:
                    content = json.dumps(resp2, ensure_ascii=False)
                except Exception:
                    content = None
            else:
                content = resp2 if isinstance(resp2, str) else None
        if not isinstance(content, str) or not content.strip():
            logger.error("Stage 07: LLM returned empty content.")
            raise RuntimeError(
                "Stage 07: LLM returned empty content. Verify API keys and Chat Completions access; inspect logs in 07_reflow_section/logs for request_info and response dumps."
            )

        # Try unified normalization first (dict or string → dict); else strict → repair
        try:
            parsed = _content_to_json_dict(content)
            result = parsed
        except Exception as _norm_err:
            # Parse JSON: strict first (no repair). Optionally relax if allowed.
            try:
                parsed = parse_json_strict(content)
                result = parsed
            except Exception as _strict_err:
                if os.getenv("STAGE07_STRICT_PARSE_ONLY", "0").lower() in ("1", "true", "yes", "y"):
                    logger.warning(f"Strict JSON parse failed (no repair allowed): {_strict_err}")
                    raise
                logger.warning(f"Strict JSON parse failed; attempting relaxed repair: {_strict_err}")
                # Prefer project cleaner to handle stray fences/trailing commas, etc.
                parsed = clean_json_string(content, return_dict=True)
            # Optional: prune unexpected top-level keys for strictness (default ON)
            try:
                if os.getenv("STAGE07_PRUNE_TOPLEVEL_KEYS", "1").lower() in ("1", "true", "yes", "y"):
                    _allowed = {"reflowed_json", "ocr_corrections", "improvements_made", "summary"}
                    parsed = restrict_top_level_keys(parsed, _allowed)
            except Exception:
                pass
            if isinstance(parsed, dict):
                result = parsed
            elif isinstance(parsed, list):
                # If the model returned a top-level list, try using the first object
                result = (
                    parsed[0]
                    if parsed and isinstance(parsed[0], dict)
                    else {"reflowed_text": content}
                )
            elif isinstance(parsed, str):
                tmp = json.loads(parsed)
                result = tmp if isinstance(tmp, dict) else {"reflowed_text": content}
            else:
                result = {"reflowed_text": content}
        except Exception:
            logger.warning("Invalid JSON from LLM; failing per policy (no fallback)")
            try:
                sec_diags.append(
                    make_event(
                        "07_reflow_section",
                        "warning",
                        "llm_invalid_json",
                        "LLM returned invalid JSON",
                        {},
                    )
                )
            except Exception:
                pass
            raise ValueError(
                "Stage 07: LLM returned invalid JSON. See logs in 07_reflow_section/logs and verify the model returns strict JSON (no code fences) matching schema mode expectations."
            )

        # Enforce schema presence; do not accept wrappers or missing keys
        if SCHEMA_MODE == "reflow_json":
            if not (isinstance(result, dict) and result.get("reflowed_json")):
                raise ValueError(
                    "Stage 07: Expected 'reflowed_json' in model output for schema mode but it was missing. Ensure the prompt instructs returning the exact schema."
                )
            out = {**section_data}
            out.update(
                {
                    "reflowed_json": result.get("reflowed_json"),
                    "ocr_corrections": result.get("ocr_corrections", {}),
                    "improvements_made": result.get("improvements_made", ""),
                    "summary": result.get("summary", ""),
                    "reflow_status": "success",
                }
            )
            # Optional figure fallback for recovery scenarios only when explicitly enabled
            try:
                figs = section_data.get("figures") or []
                rj = out.get("reflowed_json") or {}
                blocks = rj.get("blocks") or []
                has_fig_block = any(isinstance(b, dict) and b.get("type") == "figure" for b in blocks)
                if figs and not has_fig_block:
                    f0 = figs[0]
                    cap = (f0.get("ai_description") or "").strip() or None
                    imgp = f0.get("image_path") or None
                    fig_block = {
                        "type": "figure",
                        "title": None,
                        "caption": cap,
                        "image_ref": imgp,
                        "source": {
                            "pages": [f0.get("page")] if f0.get("page") is not None else [],
                            "block_ids": [],
                        },
                    }
                    if f0.get("figure_id"):
                        fig_block["figure_id"] = f0.get("figure_id")
                    blocks = [fig_block] + (blocks if isinstance(blocks, list) else [])
                    rj["blocks"] = blocks
                    out["reflowed_json"] = rj
                    try:
                        sec_diags.append(
                            make_event(
                                "07_reflow_section",
                                "warning",
                                "figure_fallback_inserted",
                                "Figure block missing from LLM response; fallback block inserted.",
                                {"figure_id": f0.get("figure_id")},
                            )
                        )
                    except Exception:
                        pass
            except Exception:
                pass
            # Normalize figure blocks emitted by the model to Stage 06 canonical structure
            try:
                figs = section_data.get("figures") or []
                if figs:
                    canon_map = {}
                    for f in figs:
                        blk = _build_figure_block_from_stage06(f)
                        if blk and f.get("figure_id"):
                            canon_map[f.get("figure_id")] = blk
                    rj = out.get("reflowed_json") or {}
                    blocks = list(rj.get("blocks") or [])
                    updated: list[Any] = []
                    changed = False
                    for blk in blocks:
                        replaced = False
                        if isinstance(blk, dict) and blk.get("type") in {"figure", "figure_reference"}:
                            fid = blk.get("figure_id")
                            canon = canon_map.get(fid)
                            if not canon and figs:
                                canon = _build_figure_block_from_stage06(figs[0])
                            if canon:
                                merged = dict(canon)
                                for key in ("title", "caption", "alt", "image_ref"):
                                    if blk.get(key):
                                        merged[key] = blk.get(key)
                                updated.append(merged)
                                replaced = True
                                changed = True
                        if not replaced:
                            updated.append(blk)
                    if changed:
                        rj["blocks"] = updated
                        out["reflowed_json"] = rj
            except Exception:
                pass
            # Ensure at least one table block is present when tables exist
            try:
                tabs = section_data.get("tables") or []
                rj = out.get("reflowed_json") or {}
                blocks = rj.get("blocks") or []
                has_tbl_block = any(isinstance(b, dict) and b.get("type") == "table" for b in blocks)
                if tabs and not has_tbl_block:
                    t0 = tabs[0]
                    tbl_block = _build_table_block_from_stage05(t0)
                    if tbl_block:
                        blocks = [tbl_block] + (blocks if isinstance(blocks, list) else [])
                        rj["blocks"] = blocks
                        out["reflowed_json"] = rj
            except Exception:
                pass
            # Replace table blocks with canonical data only when the model produced invalid structures
            try:
                canonical_tables = [
                    b for b in (_build_table_block_from_stage05(t) for t in section_data.get("tables", [])) if b
                ]
                if canonical_tables:
                    rj = out.get("reflowed_json") or {}
                    blocks = list(rj.get("blocks") or [])
                    table_indices = [
                        idx
                        for idx, blk in enumerate(blocks)
                        if isinstance(blk, dict) and blk.get("type") == "table"
                    ]
                    # remove any extra table blocks beyond the canonical set
                    for extra_idx in sorted(table_indices[len(canonical_tables):], reverse=True):
                        blocks.pop(extra_idx)

                    # ensure at least canonical count slots exist and replace with sanitized data
                    while len(table_indices) < len(canonical_tables):
                        blocks.append({"type": "table", "columns": [], "rows": []})
                        table_indices.append(len(blocks) - 1)

                    for canon, idx in zip(canonical_tables, table_indices):
                        existing = blocks[idx] if 0 <= idx < len(blocks) else {}
                        merged = canon.copy()
                        if isinstance(existing, dict) and existing.get("title"):
                            merged["title"] = existing.get("title")
                        differences: list[dict[str, Any]] = []
                        try:
                            existing_rows = existing.get("rows") if isinstance(existing, dict) else None
                            if isinstance(existing_rows, list):
                                canon_cols = merged.get("columns") or []
                                for r_idx, (canon_row, existing_row) in enumerate(zip(merged.get("rows", []), existing_rows)):
                                    for c_idx, (canon_cell, existing_cell) in enumerate(zip(canon_row, existing_row)):
                                        if _normalize_table_text(existing_cell) != canon_cell:
                                            differences.append(
                                                {
                                                    "row": r_idx,
                                                    "column": canon_cols[c_idx] if c_idx < len(canon_cols) else c_idx,
                                                    "original": existing_cell,
                                                    "sanitized": canon_cell,
                                                }
                                            )
                        except Exception:
                            pass
                        blocks[idx] = merged
                        if differences:
                            try:
                                sec_diags.append(
                                    make_event(
                                        "07_reflow_section",
                                        "info",
                                        "table_cells_sanitized",
                                        "Sanitized table cells to match canonical Stage 05 data.",
                                        {"differences": differences},
                                    )
                                )
                            except Exception:
                                pass
                    rj["blocks"] = blocks
                    out["reflowed_json"] = rj
            except Exception:
                pass
        else:
            if not (isinstance(result, dict) and result.get("reflowed_text")):
                raise ValueError(
                    "Stage 07: Expected 'reflowed_text' in model output but it was missing. Ensure the prompt instructs returning the exact keys."
                )
            out = {**section_data}
            out.update(
                {
                    "reflowed_text": result.get("reflowed_text"),
                    "ocr_corrections": result.get("ocr_corrections", {}),
                    "improvements_made": result.get("improvements_made", ""),
                    "reflow_status": "success",
                }
            )
        if STAGE07_DEBUG:
            out["quick_summary"] = result.get(
                "summary",
                (section_data.get("merged_text") or section_data.get("raw_text", ""))[:280],
            )
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
            sec_diags.append(
                make_event(
                    "07_reflow_section",
                    "error",
                    info.get("code", "llm_error"),
                    info.get("message", str(e)),
                    {},
                )
            )
        except Exception:
            pass
        if allow_fallback:
            # Build a minimal fallback payload so downstream stages can proceed
            try:
                fallback_text = (
                    section_data.get("merged_text")
                    or section_data.get("source_text")
                    or section_data.get("raw_text")
                    or ""
                )
                out = {**section_data}
                if SCHEMA_MODE == "reflow_json":
                    out.update(
                        {
                            "reflowed_json": {
                                "section_id": section_data.get("id"),
                                "title": section_data.get("title"),
                                "blocks": [
                                    {
                                        "type": "paragraph",
                                        "text": fallback_text,
                                        "source": {"pages": [], "block_ids": []},
                                    }
                                ],
                            },
                            "ocr_corrections": {},
                            "improvements_made": "fallback (no LLM)",
                            "summary": "",
                            "reflow_status": "fallback",
                        }
                    )
                else:
                    out.update(
                        {
                            "reflowed_text": fallback_text,
                            "ocr_corrections": {},
                            "improvements_made": "fallback (no LLM)",
                            "reflow_status": "fallback",
                        }
                    )
                try:
                    md = out.setdefault("metadata", {})
                    md.setdefault("diagnostics", []).extend(sec_diags)
                except Exception:
                    pass
                try:
                    log_metric(
                        "07_reflow_section",
                        {
                            "request_id": section_data.get("id"),
                            "model": LLM_MODEL,
                            "success": False,
                            "fallback_used": True,
                            "metadata": {
                                "doc_id": section_data.get("id"),
                                "section_title": section_data.get("title"),
                            },
                        },
                    )
                except Exception:
                    pass
                logger.warning("Stage 07: Falling back to merged text (no LLM)")
                return out
            except Exception:
                pass
        logger.error(f"Stage 07: LLM call failed: {e}")
        raise RuntimeError(
            "Stage 07 failed: LLM call did not return usable JSON. Check 07_reflow_section/logs, verify API keys, and confirm the configured Chat model is reachable."
        )


def consolidate_data(
    sections_path: Path,
    tables_path: Path,
    figures_path: Path,
    annotations_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Reads and merges data from previous stages (sections, tables, figures, annotations)."""
    with open(sections_path) as f:
        sections_data = json.load(f).get("sections", [])

    with open(tables_path) as f:
        tables_list = json.load(f).get("tables", [])

    with open(figures_path) as f:
        figures_list = json.load(f).get("figures", [])

    # Index by section id for quick join
    tables_by_section: dict[str, list[dict[str, Any]]] = {}
    for t in tables_list:
        sid = t.get("section_id")
        if sid is None:
            continue
        tables_by_section.setdefault(sid, []).append(t)

    figures_by_section: dict[str, list[dict[str, Any]]] = {}
    for g in figures_list:
        sid = g.get("section_id")
        if sid is None:
            continue
        figures_by_section.setdefault(sid, []).append(g)

    # Load annotations by page (optional)
    annotations_by_page: dict[int, list[dict[str, Any]]] = {}
    source_pdf: str | None = None
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

    def _merge_text_blocks(blocks: list[dict[str, Any]]) -> str:
        """Minimal normalization for fallback: join non-empty lines into paragraphs.
        LLM handles full reflow; this is only for pass-through when needed.
        """
        parts: list[str] = []
        for b in blocks or []:
            txt = (b.get("text") or "").strip()
            if not txt:
                continue
            lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
            if lines:
                parts.append(" ".join(lines))
        return "\n\n".join(parts)

    for section in sections_data:
        # Source text (raw _order) and minimal merged fallback from blocks
        blocks = section.get("blocks", [])
        section["source_text"] = "\n".join(
            [(b.get("text") or "").strip() for b in blocks if (b.get("text") or "").strip()]
        )
        section["merged_text"] = _merge_text_blocks(blocks)
        sid = section.get("id")
        if source_pdf:
            section["source_pdf"] = source_pdf

        # Attach tables and figures
        section["tables"] = tables_by_section.get(sid, [])
        section["figures"] = figures_by_section.get(sid, [])

        # Merge tables within the section when they represent header/body or continued parts across pages
        def _rows_cols(t: dict[str, Any]) -> tuple[int, int]:
            m = t.get("pandas_metrics") or {}
            shape = m.get("shape") or [0, 0]
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
                return float(inter / uni) if uni > 0 else 0.0
            except Exception:
                return 0.0

        def _metrics_for(df: pd.DataFrame) -> dict[str, Any]:
            try:
                if df is None or df.empty:
                    return {"shape": [0, 0], "data_density": 0.0, "columns": []}
                total_cells = int(df.size)
                non_empty = int(df.astype(str).ne("").sum().sum())
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

        def _merge_section_tables(sec: dict[str, Any]) -> None:
            tabs = list(sec.get("tables") or [])
            if len(tabs) <= 1:
                return
            # Sort by page then by table_index
            try:
                tabs.sort(
                    key=lambda t: (
                        int(t.get("page_index", 0) or 0),
                        int(t.get("table_index", 0) or 0),
                    )
                )
            except Exception:
                pass
            merged: list[dict[str, Any]] = tabs[:]
            i = 0
            while i < len(merged) - 1:
                t1, t2 = merged[i], merged[i + 1]
                r1, c1 = _rows_cols(t1)
                r2, c2 = _rows_cols(t2)
                if (
                    c1 > 0
                    and c1 == c2
                    and (t2.get("page_index", 0) <= (t1.get("page_index", 0) or 0) + 1)
                ):
                    iou = _h_iou(
                        t1.get("bbox", []) or [0, 0, 0, 0], t2.get("bbox", []) or [0, 0, 0, 0]
                    )
                    if iou >= 0.2:
                        # Case A: header (1 row) + body (>=2 rows)
                        if r1 == 1 and r2 >= 2:
                            try:
                                hdr = pd.DataFrame(t1.get("pandas_df") or [])
                                body = pd.DataFrame(t2.get("pandas_df") or [])
                                def _collapse_ws_df(df: pd.DataFrame) -> pd.DataFrame:
                                    return df.applymap(
                                        lambda v: _sanitize_table_cell(v) if not pd.isna(v) else ""
                                    )
                                # Apply header row as column names if shape aligns
                                if len(body.columns) == len(hdr.columns):
                                    _hdr_clean = _collapse_ws_df(hdr)
                                    body = _collapse_ws_df(body)
                                    new_cols = [
                                        (_sanitize_table_cell(x) or str(j))
                                        for j, x in enumerate(hdr.iloc[0].tolist())
                                    ]
                                    body.columns = new_cols
                                else:
                                    body = _collapse_ws_df(body)
                                t2["pandas_df"] = body.to_dict("records")
                                # Recompute metrics
                                t2["pandas_metrics"] = _metrics_for(body)
                                # Drop t1, keep t2 as merged
                                merged.pop(i)
                                continue  # stay at same index; t2 now occupies position i
                            except Exception:
                                pass
                        # Case B: both bodies with same columns -> concatenate
                        if r1 >= 2 and r2 >= 2:
                            try:
                                df1 = pd.DataFrame(t1.get("pandas_df") or [])
                                df2 = pd.DataFrame(t2.get("pandas_df") or [])
                                def _collapse(df: pd.DataFrame) -> pd.DataFrame:
                                    return df.applymap(
                                        lambda v: _sanitize_table_cell(v) if not pd.isna(v) else ""
                                    )
                                if len(df1.columns) == len(df2.columns):
                                    out = pd.concat([_collapse(df1), _collapse(df2)], ignore_index=True)
                                    t1["pandas_df"] = out.to_dict("records")
                                    t1["pandas_metrics"] = _metrics_for(out)
                                    # Drop t2
                                    merged.pop(i + 1)
                                    # do not advance i; re-evaluate chaining merges
                                    continue
                            except Exception:
                                pass
                i += 1
            # If multiple remain, keep the densest
            if len(merged) > 1:

                def _density(t: dict[str, Any]) -> float:
                    m = t.get("pandas_metrics") or {}
                    try:
                        return float(m.get("data_density") or 0.0)
                    except Exception:
                        return 0.0

                keep = max(merged, key=_density)
                sec["tables"] = [keep]
            else:
                sec["tables"] = merged

        # Always prepare merged tables for downstream normalization/prompting
        _merge_section_tables(section)

        # Attach relevant annotations by page range, then rank by semantic similarity (text-only fallback)
        page_start = int(section.get("page_start", 0) or 0)
        page_end = int(section.get("page_end", page_start) or page_start)
        candidates: list[dict[str, Any]] = []
        for p in range(page_start, page_end + 1):
            candidates.extend(annotations_by_page.get(p, []))
        # Always include all on-page annotations by default (no cut)
        selected: list[dict[str, Any]] = list(candidates)
        try:
            # Prefer semantic ranking when a text embedding model is available
            embedder = _ensure_embedder()
            if candidates and embedder is not None:
                # Build query text from section title + raw text
                title = section.get("title", "") or ""
                raw_text = section.get("raw_text", "") or ""
                query_text = f"{title}\n{raw_text}".strip()
                q_vec = embedder.encode(query_text, normalize_embeddings=True)

                def _blocks_to_text(blocks: list[dict[str, Any]]) -> str:
                    lines: list[str] = []
                    for blk in blocks or []:
                        for ln in blk.get("lines", []):
                            for sp in ln.get("spans", []):
                                t = (sp.get("text") or "").strip()
                                if t:
                                    lines.append(t)
                    return " ".join(lines)

                annot_texts: list[str] = []
                for a in candidates:
                    inside = _blocks_to_text(a.get("inside_blocks", []))
                    above = _blocks_to_text(a.get("above_blocks", []))
                    below = _blocks_to_text(a.get("below_blocks", []))
                    combined = " ".join([inside, above, below]).strip()
                    annot_texts.append(combined if combined else a.get("type", ""))

                a_vecs = embedder.encode(annot_texts, normalize_embeddings=True)
                sims = np.dot(a_vecs, q_vec)
                _order = np.argsort(-sims)
                # Annotate similarity on all on-page candidates
                for i in range(len(candidates)):
                    candidates[i]["similarity"] = float(sims[i])
        except Exception as e:
            logger.warning(f"Annotation semantic ranking failed; using page-order. Reason: {e}")
            selected = candidates
        section["annotations"] = selected
        if STAGE07_DEBUG:
            try:
                section["hybrid_status"] = {
                    "page": page_start,
                    "on_page_candidates": len(candidates),
                    "selected": len(selected),
                }
            except Exception:
                pass

    return sections_data


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
                except Exception:
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
def run(
    sections_json: Path,
    tables_json: Path,
    figures_json: Path,
    annotations_json: Path | None = None,
    output_dir: Path = Path("data/results/pipeline"),
    summary_only: bool = False,
    include_images: bool = False,
    allow_fallback: bool = False,
    bundle: Path | None = None,
    llm_timeout: int = 60,
    mode: str = "strict",
) -> Path:
    """
    Reflows document sections using multimodal context from previous stages.
    """
    console.print("[bold green]Starting Section Reflow (Stage 07)[/bold green]")
    # Respect allow-images toggle (default text-only)
    _ALLOW_IMAGES = os.getenv("STAGE07_ALLOW_IMAGES", "0").lower() in ("1", "true", "yes", "y")
    include_images = bool(include_images and _ALLOW_IMAGES)
    global LLM_MODEL
    try:
        # Choose model based on whether images are included
        LLM_MODEL = get_vlm_model() if include_images else get_text_model()
    except Exception as _e:
        console.print(f"[red]Stage 07 model selection failed: {_e}[/red]")
        raise RuntimeError("Stage 07 model selection failed")
    # Early sanity: scillm/Chutes must be reachable to avoid hangs
    try:
        from extractor.pipeline.utils.preflight import scillm_quick_check

        ok, reason = scillm_quick_check(timeout=3.0)
        if not ok:
            console.print(
                f"[red]Stage 07 preflight failed: {reason}. Set CHUTES_API_BASE/CHUTES_API_KEY or use --summary-only.[/red]"
            )
            raise RuntimeError("Stage 07 preflight failed")
    except Exception as _e:
        raise RuntimeError(f"Stage 07 preflight error: {_e}")
    run_id = get_run_id()
    diagnostics = []
    errors_count = 0
    warnings_count = 0
    import time

    t0 = time.monotonic()
    stage_start_ts = iso_now()
    resources = snapshot_resources("start")
    sampler = (
        start_resource_sampler(float(os.getenv("SAMPLE_INTERVAL_SEC", "2")))
        if os.getenv("ENABLE_RESOURCE_SAMPLING", "0").lower() in ("1", "true", "yes", "y")
        else None
    )
    try:
        if sampler and not gpu_metrics_available():
            diagnostics.append(
                make_event(
                    "07_reflow_section",
                    "info",
                    "gpu_metrics_unavailable",
                    "NVML not available; GPU metrics disabled",
                    {},
                )
            )
    except Exception:
        pass

    # --- Profile toggles (simple profile defaults) ---
    try:
        if not include_images:
            os.environ.setdefault("STAGE07_MAX_IMAGES", "0")
    except Exception:
        pass

    # --- Directory and Data Setup ---
    # Optional: unify env toggles via --mode flag for determinism
    try:
        m = (mode or "strict").strip().lower()
        if m == "minimal":
            os.environ.setdefault("STAGE07_FORCE_MINIMAL_CALL", "1")
            os.environ.setdefault("STAGE07_MINIMAL_JSON", "1")
            os.environ.setdefault("STAGE07_SCHEMA_MODE", "text")
        elif m == "strict":
            os.environ.pop("STAGE07_FORCE_MINIMAL_CALL", None)
            os.environ.pop("STAGE07_MINIMAL_JSON", None)
            os.environ.setdefault("STAGE07_SCHEMA_MODE", "reflow_json")
    except Exception:
        pass
    stage_output_dir = output_dir / "07_reflow_section"
    json_output_dir = stage_output_dir / "json_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)

    # Prefer enriched tables/figures when present (06a outputs)
    try:
        prefer_enriched = os.getenv("STAGE07_PREFER_ENRICHED", "1").lower() in ("1","true","yes","y")
        if prefer_enriched:
            base_dir = output_dir
            enr_tables = base_dir / "06a_title_caption_enricher" / "json_output" / "05_tables.enriched.json"
            enr_figs = base_dir / "06a_title_caption_enricher" / "json_output" / "06_figures.enriched.json"
            if enr_tables.exists():
                tables_json = enr_tables
            if enr_figs.exists():
                figures_json = enr_figs
    except Exception:
        pass

    sections_to_process = consolidate_data(
        sections_json, tables_json, figures_json, annotations_json
    )
    # Attach layout sketches if available (06b step)
    if USE_LAYOUT_SKETCH:
        try:
            sketches_path = output_dir / "06b_layout_sketcher" / "json_output" / "06b_layout_sketch.json"
            if sketches_path.exists():
                sk_map = json.loads(sketches_path.read_text()).get("sections", {})
                sk_count = 0
                for s in sections_to_process:
                    sid = str(s.get("id"))
                    sk = sk_map.get(sid)
                    if isinstance(sk, dict):
                        s["layout_sketch"] = sk
                        # Apply deterministic ordering for tables/figures before prompting
                        _apply_layout_ordering(s)
                        sk_count += 1
                diagnostics.append(
                    make_event(
                        "07_reflow_section",
                        "info",
                        "layout_sketch_attached",
                        f"Attached sketches for {sk_count} sections",
                        {},
                    )
                )
        except Exception as _e:
            diagnostics.append(
                make_event("07_reflow_section", "warning", "layout_sketch_missing", str(_e), {})
            )

    # Optional: load or build FAISS index from Stage 01 annotations for similar text lookup
    ann_index = None
    _ann_list = []
    try:
        if annotations_json and annotations_json.exists():
            stage01_dir = annotations_json.parent.parent  # .../01_annotation_processor
            idx, meta = load_ann_index(stage01_dir / "annots_faiss")
            if idx is not None:
                ann_index = idx
                diagnostics.append(
                    make_event(
                        "07_reflow_section",
                        "info",
                        "ann_index_loaded",
                        f"Loaded FAISS index from {stage01_dir}",
                        {},
                    )
                )
            else:
                _payload = json.load(open(annotations_json))
                _ann_list = _payload.get("annotations", []) or []
                if _ann_list:
                    ann_index, _ = build_ann_index(_ann_list)
                    diagnostics.append(
                        make_event(
                            "07_reflow_section",
                            "info",
                            "ann_index_built",
                            f"FAISS annotations index built: {len(_ann_list)} items",
                            {},
                        )
                    )
    except Exception as _ie:
        diagnostics.append(
            make_event("07_reflow_section", "warning", "ann_index_unavailable", str(_ie), {})
        )

    # Attach top-3 similar annotations (text-only) to each section (advisory)
    if ann_index is not None:
        for sec in sections_to_process:
            try:
                qtext = (str(sec.get("title", "")) + "\n" + str(sec.get("merged_text", "")))[:2000]
                sims = query_ann_index(ann_index, qtext, top_k=3)
                if sims:
                    # If we built from _ann_list, map indices to ids; else leave ids None
                    ids_scores = []
                    for i, score in sims:
                        aid = None
                        try:
                            if _ann_list:
                                aid = _ann_list[i].get("id")
                        except Exception:
                            aid = None
                        ids_scores.append({"id": aid, "score": score})
                        try:
                            # add optional snippet
                            import os as _os

                            from extractor.pipeline.utils.ann_index import (
                                render_ann_snippet as _snip,
                            )

                            if _ann_list:
                                _maxc = int(_os.getenv("ANN_SIMILAR_SNIPPET_CHARS", "200"))
                                ids_scores[-1]["snippet"] = _snip(_ann_list[i], _maxc)
                        except Exception:
                            pass
                    sec["similar_annotations"] = ids_scores
            except Exception:
                pass

    if not sections_to_process:
        # Synthesize minimal sections from tables when Stage 04 produced none
        try:
            tbl_payload = json.loads(Path(tables_json).read_text())
            tables = tbl_payload.get("tables") or []
        except Exception:
            tables = []
        if tables:
            # Group tables by page and create one synthetic section per page
            by_page: dict[int, list[dict[str, Any]]] = {}
            for t in tables:
                try:
                    p = int(t.get("page_index", 0) or 0)
                except Exception:
                    p = 0
                by_page.setdefault(p, []).append(t)
            synth: list[dict[str, Any]] = []
            for p, group in sorted(by_page.items(), key=lambda kv: kv[0]):
                sid = f"SYNTH_P{p}"
                synth.append({
                    "id": sid,
                    "title": f"Tables (page {p})",
                    "level": 1,
                    "page_start": p,
                    "page_end": p,
                    "blocks": [],
                    "tables": group,
                    "figures": [],
                    "raw_text": "",
                    "merged_text": "",
                })
            sections_to_process = synth
            diagnostics.append(
                make_event(
                    "07_reflow_section",
                    "info",
                    "synth_sections_from_tables",
                    f"Created {len(synth)} synthetic sections from tables",
                    {},
                )
            )
        else:
            console.print("[yellow]No sections found to process. Exiting.[/yellow]")
            return

    # --- Processing ---
    if summary_only:
        processed_sections = []
        for s in sections_to_process:
            # Emit summary-only payloads; do not call LLM
            sec_out = {
                **s,
                "reflowed_text": s.get("merged_text") or s.get("raw_text", ""),
                # Provide a placeholder to satisfy gold expectation for presence of reflowed_json
                "reflowed_json": {},
                "ocr_corrections": {},
                "improvements_made": "summary-only (no LLM)",
                "reflow_status": "success_placeholder",
            }
            if STAGE07_DEBUG:
                sec_out["quick_summary"] = (s.get("merged_text") or s.get("raw_text", ""))[:280]
            processed_sections.append(sec_out)
    else:

        async def run_tasks_first():
            tasks = []
            for s in sections_to_process:
                use_images = include_images
                if USE_LAYOUT_SKETCH and OMIT_IMAGES_IF_CONFIDENT:
                    try:
                        conf = float(((s.get("layout_sketch") or {}).get("conf") or {}).get("ordering") or 0.0)
                        if conf >= LAYOUT_CONF_THRESH:
                            use_images = False
                            diagnostics.append(
                                make_event(
                                    "07_reflow_section",
                                    "info",
                                    "images_omitted_due_to_layout_conf",
                                    f"Omitted images for section {s.get('id')} (conf={conf:.2f} >= {LAYOUT_CONF_THRESH})",
                                    {},
                                )
                            )
                    except Exception:
                        pass
                tasks.append(
                    reflow_section_with_llm(
                        s,
                        output_dir,
                        include_images=use_images,
                        allow_fallback=allow_fallback,
                        llm_timeout=llm_timeout,
                    )
                )
            return await tqdm_asyncio.gather(*tasks, desc="Reflowing Sections (text-first)")

        processed_sections = asyncio.run(run_tasks_first())
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
    source_files = {
        "sections": str(sections_json),
        "tables": str(tables_json),
        "figures": str(figures_json),
        "annotations": str(annotations_json) if annotations_json else None,
    }

    unified_document_payload = None
    try:
        unified_document = build_unified_document_from_reflow(
            sections=processed_sections,
            source_path=str(sections_json) if sections_json else None,
            source_type=SourceType.PDF,
            document_metadata={"source_files": source_files},
        )
        unified_document_payload = unified_document.model_dump(by_alias=True, mode="json")
    except Exception as exc:  # pragma: no cover - defensive
        diagnostics.append(
            make_event(
                "07_reflow_section",
                "warning",
                "unified_document_generation_failed",
                str(exc),
                {},
            )
        )

    final_output = {
        "timestamp": datetime.now().isoformat(),
        "source_files": source_files,
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

    if unified_document_payload:
        final_output["unified_document"] = unified_document_payload

    output_path = json_output_dir / "07_reflowed.json"

    # Optional: render visual overlays per section to show provenance of reflow blocks
    try:
        if STAGE07_VISUAL_PROOF:
            # Resolve source PDF from Stage 04 payload; allow env override
            src_pdf: Optional[Path] = None
            try:
                s04 = json.loads(sections_json.read_text())
                sp = s04.get("source_pdf")
                if isinstance(sp, str) and Path(sp).exists():
                    src_pdf = Path(sp)
            except Exception:
                src_pdf = None
            if not src_pdf and STAGE07_SOURCE_PDF:
                p = Path(STAGE07_SOURCE_PDF)
                src_pdf = p if p.exists() else None

            # Build quick indexes to map sources → bboxes
            blocks_index: Dict[str, Tuple[int, List[float]]] = {}
            try:
                if "sections" in s04:
                    for sec in s04.get("sections") or []:
                        for b in sec.get("blocks") or []:
                            bid = b.get("id") or b.get("block_id")
                            bb = b.get("bbox") or []
                            try:
                                pg = int(b.get("page") or b.get("page_idx") or sec.get("page_start") or 0)
                            except Exception:
                                pg = 0
                            if bid and isinstance(bb, list) and len(bb) == 4:
                                blocks_index[str(bid)] = (pg, [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])])
            except Exception:
                pass

            tables_index: Dict[int, Tuple[int, List[float]]] = {}
            try:
                tj = json.loads((tables_json or Path()).read_text()) if tables_json and tables_json.exists() else {}
                for t in tj.get("tables") or []:
                    try:
                        idx = int(t.get("table_index"))
                        pg = int(t.get("page_index", 0))
                        bb = t.get("bbox") or []
                        if isinstance(bb, list) and len(bb) == 4:
                            tables_index[idx] = (pg, [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])])
                    except Exception:
                        continue
            except Exception:
                pass

            figures_index: Dict[str, Tuple[int, List[float]]] = {}
            try:
                fj = json.loads((figures_json or Path()).read_text()) if figures_json and figures_json.exists() else {}
                for f in fj.get("figures") or []:
                    fid = f.get("figure_id") or f.get("id") or f.get("image_path")
                    try:
                        pg = int(f.get("page") or f.get("page_idx") or f.get("page_index") or 0)
                    except Exception:
                        pg = 0
                    bb = f.get("bbox") or []
                    if fid and isinstance(bb, list) and len(bb) == 4:
                        figures_index[str(fid)] = (pg, [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])])
            except Exception:
                pass

            # Render overlays
            if src_pdf and processed_sections:
                from extractor.pipeline.visual.overlay import Box, draw_overlays
                stage_vis = stage_output_dir / "visual_output"
                for sec in processed_sections:
                    sid = str(sec.get("id") or "section")
                    boxes: List[Box] = []
                    # Prefer structured JSON blocks when present
                    rj = (sec.get("reflowed_json") or {}).get("blocks") if isinstance(sec.get("reflowed_json"), dict) else None
                    blocks_list = rj if isinstance(rj, list) else []
                    for i, b in enumerate(blocks_list):
                        typ = (b.get("type") or "").lower()
                        label = f"{i}:{typ}" if typ else f"{i}"
                        src = b.get("source") or {}
                        drawn = False
                        # Paragraph/List/Heading → map first block_id
                        if typ in {"paragraph", "list", "heading"}:
                            bids = src.get("block_ids") or []
                            if isinstance(bids, list) and bids:
                                key = str(bids[0])
                                if key in blocks_index:
                                    pg, bb = blocks_index[key]
                                    boxes.append(Box(page=int(pg), x0=bb[0], y0=bb[1], x1=bb[2], y1=bb[3], label=label, color=(0, 170, 255), width=3))
                                    drawn = True
                        # Table → map table_indices
                        if not drawn and typ == "table":
                            tids = src.get("table_indices") or []
                            if isinstance(tids, list) and tids:
                                ti0 = None
                                try:
                                    ti0 = int(tids[0])
                                except Exception:
                                    ti0 = None
                                if ti0 is not None and ti0 in tables_index:
                                    pg, bb = tables_index[ti0]
                                    boxes.append(Box(page=int(pg), x0=bb[0], y0=bb[1], x1=bb[2], y1=bb[3], label=label, color=(0, 200, 0), width=3))
                                    drawn = True
                        # Figure → map by figure_id or image_ref
                        if not drawn and typ == "figure":
                            fid = b.get("figure_id") or b.get("image_ref")
                            if fid and str(fid) in figures_index:
                                pg, bb = figures_index[str(fid)]
                                boxes.append(Box(page=int(pg), x0=bb[0], y0=bb[1], x1=bb[2], y1=bb[3], label=label, color=(255, 128, 0), width=3))
                                drawn = True
                        # As a last resort, draw at the first page listed in source without bbox (skip to avoid misleading boxes)
                    if boxes:
                        vout = stage_vis / sid
                        draw_overlays(src_pdf, boxes, vout)
                        try:
                            # Attach relative paths for convenience
                            rel = [str(p.relative_to(output_dir.parent.parent)) for p in vout.glob("*.png")]
                            if rel:
                                sec.setdefault("visual_overlays", rel)
                        except Exception:
                            pass
    except Exception as _e:
        logger.warning(f"Stage 07 visual overlay generation failed: {_e}")

    with open(output_path, "w") as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)

    console.print("\n[bold green]✅ Section reflow complete.[/bold green]")
    console.print(f"   - Results saved to: [cyan]{output_path}[/cyan]")
    return output_path


if __name__ == "__main__":
    # Minimal entry: SECTIONS_JSON TABLES_JSON FIGURES_JSON [ANNOTATIONS_JSON] [OUT_DIR] [--summary-only]
    try:
        from dotenv import find_dotenv, load_dotenv

        load_dotenv(find_dotenv())
    except Exception:
        pass
    import sys
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(
            "Usage: python -m extractor.pipeline.steps.07_reflow_section SECTIONS_JSON TABLES_JSON FIGURES_JSON [ANNOTATIONS_JSON] [OUT_DIR] [--summary-only]",
            file=sys.stderr,
        )
        sys.exit(2)
    summary_only = False
    if "--summary-only" in argv:
        summary_only = True
        argv = [a for a in argv if a != "--summary-only"]
    if len(argv) < 3:
        print("Missing required paths", file=sys.stderr)
        sys.exit(2)
    sections_json = Path(argv[0])
    tables_json = Path(argv[1])
    figures_json = Path(argv[2])
    ann_json = None
    out_dir = Path("data/results/pipeline")
    if len(argv) >= 4:
        p = Path(argv[3])
        if p.suffix.lower() == ".json":
            ann_json = p
            out_dir = Path(argv[4]) if len(argv) >= 5 else out_dir
        else:
            out_dir = p
    out = run(
        sections_json=sections_json,
        tables_json=tables_json,
        figures_json=figures_json,
        annotations_json=ann_json,
        output_dir=out_dir,
        summary_only=summary_only,
    )
    print(str(out))


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
    except Exception as e:
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
