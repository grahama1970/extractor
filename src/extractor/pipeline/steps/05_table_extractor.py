#!/usr/bin/env python3
"""
Pipeline Stage 5: Table Extraction using Camelot
==============================================

This stage extracts tables from PDFs using Camelot's lattice detection,
which provides more accurate table extraction than pdfplumber.

Key Features:
- Multi-strategy approach (lattice with different settings)
- Intelligent padding for table visualization
- Rich pandas metrics for downstream analysis
- Handles multi-page tables
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import re
from datetime import datetime

# Direct imports - fail fast
try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF (fitz) not installed. Stage 05 requires it.", file=sys.stderr)
    raise
import pandas as pd

try:
    from camelot import io as camelot_io
except ImportError:
    print(
        "Camelot is required for Stage 05 (table extraction). Please install camelot-py.",
        file=sys.stderr,
    )
    raise
from dotenv import load_dotenv, find_dotenv
from loguru import logger
from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.table_extractor_utils import (
    _stable_table_hash,
    _should_assist,
    _headers_from_table,
    _apply_headers,
    _extract_table_text_for_heuristics,
    sanitize_cell,
    fragmentation_score,
    should_retry_fragmentation,
    has_fragmentation_improvement,
    should_replace_table,
    coalesce_repeated_header_rows,
)
# Import from new utils/tables package (extracted functions)
from extractor.pipeline.utils.tables import (
    generate_pandas_metrics as _generate_pandas_metrics,
    score_table as _score_table,
    iou as _table_iou,
    horizontal_iou as _table_h_iou,
)
from rich.console import Console
from extractor.pipeline.utils.diagnostics import (
    start_resource_sampler,
    stop_resource_sampler,
    get_run_id,
    iso_now,
    make_event,
    snapshot_resources,
    build_stage_timings,
    gpu_metrics_available,
)
from extractor.pipeline.utils.step_sanity import run_step_sanity
# SciLLM Router builder (OpenAI-compatible); avoid direct SDK calls in steps
from extractor.pipeline.utils.scillm_router import get_text_router
from extractor.pipeline.steps.scillm_preflight_validator import quick_scillm_check
from extractor.pipeline.utils.debug_utils import log_timing, write_jsonl, ensure_logs_dir



# --- Initialization ---
if not load_dotenv(find_dotenv()):
    print("Warning: .env not found; continuing with process environment.", file=sys.stderr)

logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{function}:{line}</cyan> - <level>{message}</level>",
)

console = Console()
STEP_NAME = "05_table_extractor"


def sanity() -> int:
    return run_step_sanity(STEP_NAME)

# Camelot extraction strategies
CAMELOT_STRATEGIES = {
    "lattice_default": {
        "flavor": "lattice",
        "params": {"process_background": False, "line_scale": 15},
    },
    "lattice_strong": {
        "flavor": "lattice",
        "params": {"process_background": False, "line_scale": 40},
    },
    "lattice_sensitive": {
        "flavor": "lattice",
        "params": {"process_background": False, "line_scale": 5},
    },
    # Fallback for text-lined tables without ruling lines
    "stream_default": {
        "flavor": "stream",
        "params": {"edge_tol": 50},
    },
}

# Padding ratios for table image extraction
VERTICAL_PADDING_RATIO = float(os.getenv("TABLE_VERTICAL_PADDING_RATIO", 0.30))
HORIZONTAL_PADDING_RATIO = float(os.getenv("TABLE_HORIZONTAL_PADDING_RATIO", 0.07))
PYMUPDF_DPI = int(os.getenv("TABLE_EXTRACTION_DPI", 200))

# Stitching/overlap and filtering thresholds (env-configurable)
TABLE_STITCH_MIN_HORIZONTAL_IOU = float(os.getenv("TABLE_STITCH_MIN_HORIZONTAL_IOU", 0.2))
TABLE_STITCH_ALLOW_NEXT_PAGE = os.getenv("TABLE_STITCH_ALLOW_NEXT_PAGE", "true").lower() in (
    "1",
    "true",
    "yes",
    "y",
)
TABLE_FILTER_MIN_DENSITY = float(os.getenv("TABLE_FILTER_MIN_DENSITY", 0.15))
TABLE_FILTER_MIN_ROWS = int(os.getenv("TABLE_FILTER_MIN_ROWS", 3))
TABLE_HEADER_DUP_MIN_MATCH = float(os.getenv("TABLE_HEADER_DUP_MIN_MATCH", 0.5))

# Multi-page behavior
TABLE_MULTI_PAGE_MERGE_ENABLED = os.getenv("TABLE_MULTI_PAGE_MERGE_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
    "y",
)
TABLE_MULTI_PAGE_MERGE_MIN_IOU = float(os.getenv("TABLE_MULTI_PAGE_MERGE_MIN_IOU", 0.3))

# Selection behavior (quick win: stop data loss)
# When true, keep legacy behavior of selecting exactly one primary table per page.
# Default is false: keep ALL tables; let downstream consolidation (Stage 07) decide.
TABLE_SELECT_ONE_PER_PAGE = os.getenv("TABLE_SELECT_ONE_PER_PAGE", "false").lower() in (
    "1",
    "true",
    "yes",
    "y",
)
# Feature toggles (env-configurable)
# Important: Stage 05 shall NOT merge/stitch tables by default. Merging happens in Stage 07.
# Default this feature OFF to avoid header/body stitching at this stage.
TABLE_HEADER_STITCHING_ENABLED = os.getenv("TABLE_HEADER_STITCHING_ENABLED", "false").lower() in (
    "1",
    "true",
    "yes",
    "y",
)
TABLE_HEADER_DEDUP_ENABLED = os.getenv("TABLE_HEADER_DEDUP_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
    "y",
)
TABLE_HEADER_COALESCE_ENABLED = os.getenv("TABLE_HEADER_COALESCE_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
    "y",
)
TABLE_HEADER_REPEAT_MIN_MATCH = float(os.getenv("TABLE_HEADER_REPEAT_MIN_MATCH", 0.6))
FRAGMENTATION_RETRY_THRESHOLD = max(
    0, int(os.getenv("TABLE_FRAGMENTATION_RETRY_THRESHOLD", 0))
)
FRAGMENTATION_IMPROVEMENT_MIN = max(
    1, int(os.getenv("TABLE_FRAGMENTATION_MIN_IMPROVEMENT", 1))
)

# --- Core Functions ---

## moved helpers into extractor.pipeline.utils.table_extractor_utils

## moved

## moved

## moved

def _attach_llm_assist_headers(result: Dict[str, Any], stage_dir: Path) -> None:
    sidecar = stage_dir / "05_tables_llm_assist.json"
    try:
        side_data = json.loads(sidecar.read_text()) if sidecar.exists() else {}
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        side_data = {}

    # SciLLM-only: resolve model from TABLE_LLM_ASSIST_MODEL or CHUTES_TEXT_MODEL.
    # Do not fall back to any LITELLM_* envs.
    model = (os.getenv("TABLE_LLM_ASSIST_MODEL") or os.getenv("CHUTES_TEXT_MODEL") or "").strip()
    if not model:
        logger.debug("LLM assist disabled: no TABLE_LLM_ASSIST_MODEL/CHUTES_TEXT_MODEL set")
        # log skip at global RUN_RESULTS_DIR
        log_timing(
            "05_table_extractor",
            {"attempt": "llm_assist_headers_skip", "outcome": "skip", "reason": "model_unavailable"},
            stage_dir=stage_dir,
        )
        return
    tables = result.get("tables") or []
    # Budget gating (tokens/cost)
    try:
        tokens_budget = int(os.getenv("STAGE05_TOKENS_BUDGET", "120000"))
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        tokens_budget = 0
    cost_budget = float(os.getenv("STAGE05_COST_BUDGET_USD", "0") or 0)
    budget_enforce = os.getenv("STAGE05_BUDGET_ENFORCE", "true").lower() in ("1","true","yes","y")
    tokens_used = 0
    cost_used = 0.0
    # Token usage log path
    rd = os.getenv("RUN_RESULTS_DIR")
    token_logs_dir = ensure_logs_dir(Path(rd), "05_table_extractor") if rd else stage_dir
    updated = 0
    for t in tables:
        try:
            pm = t.get("pandas_metrics") or {}
            shape = pm.get("shape") or [0, 0]
            rows = int(shape[0] or 0) if isinstance(shape, (list, tuple)) else 0
            cols = int(shape[1] or 0) if isinstance(shape, (list, tuple)) else 0
            force_low_dim = (rows == 1) or (cols == 1)
            if not (force_low_dim or _should_assist(t)):
                log_timing(
                    "05_table_extractor",
                    {
                        "attempt": "llm_assist_headers_skip",
                        "outcome": "skip",
                        "reason": "doc_filtered",
                        "table_hash": _stable_table_hash(t),
                    },
                    stage_dir=stage_dir,
                )
                continue
            headers_in = _headers_from_table(t)
            # Prefer first-row cell texts when (a) headers missing, or (b) numeric/generic headers from Camelot
            try:
                shp = (t.get("pandas_metrics") or {}).get("shape") or []
                r = int(shp[0] or 0) if isinstance(shp, (list, tuple)) else 0
                use_row0 = (r == 1) and (not headers_in or all(str(h).strip().isdigit() for h in headers_in))
                if use_row0:
                    df0 = (t.get("pandas_df") or [])
                    if isinstance(df0, list) and df0:
                        row0 = df0[0]
                        if isinstance(row0, dict):
                            headers_in = [str(v).strip() for v in row0.values()]
                        elif isinstance(row0, list):
                            headers_in = [str(v).strip() for v in row0]
            except Exception as exc:
                log_stage_error('05_table_extractor', exc, {'context': '05'})
                raise
                pass
            if not headers_in:
                log_timing(
                    "05_table_extractor",
                    {
                        "attempt": "llm_assist_headers_skip",
                        "outcome": "skip",
                        "reason": "short_headers",
                        "table_hash": _stable_table_hash(t),
                    },
                    stage_dir=stage_dir,
                )
                continue
            table_hash = _stable_table_hash(t)
            cache_key = f"assist:{table_hash}:{model}"
            cached = side_data.get(cache_key)
            if cached and isinstance(cached.get("headers"), list) and len(cached["headers"]) == len(headers_in):
                t["llm_assist"] = {"model": model, "patch": cached}
                # Metadata-only: record inferred headers
                t["header_inferred"] = [sanitize_cell(h) for h in cached["headers"]]
                t["header_provenance"] = "llm_assist"
                log_timing(
                    "05_table_extractor",
                    {
                        "attempt": "llm_assist_headers",
                        "outcome": "ok",
                        "cached": True,
                        "table_hash": table_hash,
                    },
                    stage_dir=stage_dir,
                )
                updated += 1
                continue
            # Budget gate before making a new call
            if budget_enforce and ((tokens_budget and tokens_used >= tokens_budget) or (cost_budget and cost_used >= cost_budget)):
                log_timing(
                    "05_table_extractor",
                    {
                        "attempt": "llm_assist_headers_skip",
                        "outcome": "skip",
                        "reason": "budget_exceeded",
                        "table_hash": table_hash,
                        "tokens_used": tokens_used,
                        "tokens_limit": tokens_budget,
                        "cost_used_usd": round(cost_used, 6),
                        "cost_limit_usd": cost_budget or None,
                    },
                    stage_dir=stage_dir,
                )
                write_jsonl(token_logs_dir, "token_usage.jsonl", {
                    "ts": datetime.utcnow().isoformat()+"Z",
                    "event": "assist_skipped",
                    "reason": "budget_exceeded",
                    "table_hash": table_hash,
                    "tokens_used": tokens_used,
                    "tokens_limit": tokens_budget,
                    "cost_used_usd": round(cost_used, 6),
                    "cost_limit_usd": cost_budget or None,
                })
                continue
            # Build strict JSON prompt
            system = (
                "You are a strict normalizer for table column headers.\n"
                "Rules: Do not invent, add, or reorder columns.\n"
                "Return JSON: {\"headers\": [..]} with the same length as input.\n"
            )
            user = json.dumps({"headers_input": headers_in}, ensure_ascii=False)
            import asyncio as _asyncio
            import time as _time
            async def _call():
                router = get_text_router()
                resp = await router.acompletion(
                    model="chutes/text",
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": [{"type": "text", "text": user}]},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0,
                    timeout=int(os.getenv("SC_TIMEOUT_STAGE_05_ASSIST", os.getenv("TABLE_LLM_ASSIST_TIMEOUT", "20"))),
                    max_tokens=int(os.getenv("TABLE_LLM_ASSIST_MAX_TOKENS", "256")),
                )
                return resp
            _t0 = _time.monotonic()
            try:
                resp = _asyncio.run(_call())
                _elapsed_ms = int((_time.monotonic() - _t0) * 1000)
                # Extract content and usage
                content = getattr(resp, "choices", [{}])[0].get("message", {}).get("content", "")
                usage = getattr(resp, "usage", None) or {}
                served_model = getattr(resp, "model", None)
                # Update budgets
                try:
                    tokens_used += int(usage.get("prompt_tokens") or 0) + int(usage.get("completion_tokens") or 0)
                except Exception as exc:
                    log_stage_error('05_table_extractor', exc, {'context': '05'})
                    raise
                    pass
                # Optional: cost tracking left as placeholder (provider-specific); keep zero unless integrated
                write_jsonl(token_logs_dir, "token_usage.jsonl", {
                    "ts": datetime.utcnow().isoformat()+"Z",
                    "event": "assist_used",
                    "table_hash": table_hash,
                    "model": served_model,
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                    "tokens_used_cumulative": tokens_used,
                })
                log_timing(
                    "05_table_extractor",
                    {
                        "attempt": "llm_assist_headers",
                        "outcome": "ok",
                        "route_name": "chutes/text",
                        "model": served_model,
                        "latency_ms": _elapsed_ms,
                        "timeout_s": int(os.getenv("SC_TIMEOUT_STAGE_05_ASSIST", os.getenv("TABLE_LLM_ASSIST_TIMEOUT", "20"))),
                        "retries_conf": int(os.getenv("LITELLM_MAX_RETRIES", "0")),
                        "tokens_in": usage.get("prompt_tokens"),
                        "tokens_out": usage.get("completion_tokens"),
                        "table_hash": table_hash,
                        "cached": False,
                    },
                    stage_dir=stage_dir,
                )
            except Exception as exc:
                log_stage_error('05_table_extractor', exc, {'context': '05'})
                raise
                _elapsed_ms = int((_time.monotonic() - _t0) * 1000)
                log_timing(
                    "05_table_extractor",
                    {
                        "attempt": "llm_assist_headers",
                        "outcome": "exception",
                        "exception": type(e).__name__,
                        "exception_msg": str(e)[:300],
                        "latency_ms": _elapsed_ms,
                        "timeout_s": int(os.getenv("SC_TIMEOUT_STAGE_05_ASSIST", os.getenv("TABLE_LLM_ASSIST_TIMEOUT", "20"))),
                        "table_hash": table_hash,
                    },
                    stage_dir=stage_dir,
                )
                raise
            try:
                patch = json.loads(content) if content else None
            except Exception as exc:
                log_stage_error('05_table_extractor', exc, {'context': '05'})
                raise
                log_timing(
                    "05_table_extractor",
                    {
                        "attempt": "llm_assist_headers_parse",
                        "outcome": "parse_error",
                        "parse_error_message": str(pe)[:200],
                        "table_hash": table_hash,
                    },
                    stage_dir=stage_dir,
                )
                patch = None
            if not isinstance(patch, dict):
                continue
            new_headers = patch.get("headers")
            if not isinstance(new_headers, list) or len(new_headers) != len(headers_in):
                log_timing(
                    "05_table_extractor",
                    {
                        "attempt": "llm_assist_headers_parse",
                        "outcome": "parse_error",
                        "reason": "schema_mismatch",
                        "table_hash": table_hash,
                    },
                    stage_dir=stage_dir,
                )
                continue
            # normalize whitespace
            new_headers = [" ".join(str(h).split()) for h in new_headers]
            t["llm_assist"] = {"model": model, "patch": {"headers": new_headers}}
            # Metadata-only: do not mutate the DataFrame; record inferred headers instead
            t["header_inferred"] = [sanitize_cell(h) for h in new_headers]
            t["header_provenance"] = "llm_assist"
            side_data[cache_key] = {"headers": new_headers}
            updated += 1
        except Exception as exc:
            log_stage_error('05_table_extractor', exc, {'context': '05'})
            raise
            logger.warning(f"LLM assist header patch failed for table: {e}")
            log_timing(
                "05_table_extractor",
                {
                    "attempt": "llm_assist_headers",
                    "outcome": "exception",
                    "exception": type(e).__name__,
                    "exception_msg": str(e)[:300],
                    "table_hash": _stable_table_hash(t),
                },
                stage_dir=stage_dir,
            )
            continue

    try:
        if updated:
            sidecar.write_text(json.dumps(side_data, ensure_ascii=False, indent=2))
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        logger.warning(f"Failed to persist LLM assist sidecar: {e}")
        

def _demote_table_headers_to_text(result: Dict[str, Any]) -> None:
    """Detect one-line numbered headings captured as small tables and emit demoted text blocks for Stage 04.

    Adds result["demoted_text_blocks"]= [{page_idx, bbox, text}] when STAGE05_DEMOTE_TABLE_HEADERS=1.
    """
    if os.getenv("STAGE05_DEMOTE_TABLE_HEADERS", "1").lower() not in {"1","true","yes","y"}:
        return
    import re
    pat = re.compile(r"^(?:\d+\.){1,6}\s+\S.*")
    demoted: List[Dict[str, Any]] = []
    for t in result.get("tables") or []:
        try:
            pm = t.get("pandas_metrics") or {}
            shape = pm.get("shape") or [0, 0]
            rows = int(shape[0] or 0)
            cols = int(shape[1] or 0)
        except Exception as exc:
            log_stage_error('05_table_extractor', exc, {'context': '05'})
            raise
            rows, cols = 0, 0
        if cols and cols > 2:
            continue
        if rows and rows > int(os.getenv("STAGE05_DEMOTE_MAX_ROWS", "4")):
            continue
        cells: List[str] = []
        src = t.get("pandas_df_raw") or t.get("pandas_df") or []
        if isinstance(src, list):
            for r in src[:8]:
                if isinstance(r, dict):
                    cells.extend([str(v).strip() for v in r.values()])
                elif isinstance(r, list):
                    cells.extend([str(v).strip() for v in r])
        head = next((c for c in cells if c), None)
        if not head or not pat.match(head):
            continue
        if head.endswith('.') or head.endswith(';'):
            continue
        try:
            if t.get("page_index") is not None:
                p = int(t.get("page_index"))
            else:
                p = int(t.get("page_number", 1)) - 1
        except Exception as exc:
            log_stage_error('05_table_extractor', exc, {'context': '05'})
            raise
            p = 0
        bbox = t.get("bbox") or []
        demoted.append({"page_idx": p, "bbox": bbox, "text": head})
    if demoted:
        result["demoted_text_blocks"] = demoted


## moved to utils: _extract_table_text_for_heuristics


def _demote_sentence_like_single_row_tables(result: Dict[str, Any]) -> None:
    """Demote obvious single-row sentence-like tables to text blocks.

    Heuristic: rows==1 and the joined cell text looks like a sentence
    (>=6 words and ends with . ! or ? or has typical sentence punctuation).
    """
    if os.getenv("STAGE05_DEMOTE_SENTENCE_ROW", "1").lower() not in {"1","true","yes","y"}:
        return
    import re
    tables = list(result.get("tables") or [])
    keep: List[Dict[str, Any]] = []
    demoted: List[Dict[str, Any]] = result.get("demoted_text_blocks", []) or []
    for t in tables:
        pm = (t.get("pandas_metrics") or {}).get("shape") or []
        rows = int(pm[0]) if len(pm) > 0 and str(pm[0]).isdigit() else None
        if rows != 1:
            keep.append(t)
            continue
        txt = _extract_table_text_for_heuristics(t)
        words = len(txt.split())
        looks_sentence = words >= 6 and bool(re.search(r"[\.!?]\s*$", txt))
        if looks_sentence:
            try:
                p = int(t.get("page_index") if t.get("page_index") is not None else int(t.get("page_number", 1)) - 1)
            except Exception as exc:
                log_stage_error('05_table_extractor', exc, {'context': '05'})
                raise
                p = 0
            demoted.append({"page_idx": p, "bbox": t.get("bbox") or [], "text": txt, "reason": "sentence_like_single_row"})
        else:
            keep.append(t)
    result["tables"] = keep
    if demoted:
        result["demoted_text_blocks"] = demoted


def generate_pandas_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """Generate comprehensive metrics from a DataFrame for analysis."""
    if df.empty:
        return {"shape": [0, 0], "error": "Empty DataFrame"}

    total_cells = df.size
    non_empty_cells = df.astype(str).ne("").sum().sum()

    metrics = {
        "shape": list(df.shape),
        "columns": [str(c) for c in df.columns],
        "dtypes": {str(k): str(v) for k, v in df.dtypes.to_dict().items()},
        "null_counts": {str(k): int(v) for k, v in df.isnull().sum().to_dict().items()},
        "total_cells": int(total_cells),
        "non_empty_cells": int(non_empty_cells),
        "data_density": float(non_empty_cells / total_cells) if total_cells > 0 else 0.0,
    }
    return metrics


def score_table(df: pd.DataFrame) -> float:
    """Score a table based on non-empty cell count."""
    if df.empty:
        return 0.0
    return float(df.astype(str).ne("").sum().sum())


## moved to utils: sanitize_cell


## moved to utils: fragmentation_score


## moved to utils: should_retry_fragmentation


## moved to utils: has_fragmentation_improvement


## moved to utils: should_replace_table


def try_camelot_strategy(
    pdf_path: Path,
    page_num: int,
    strategy: Dict[str, Any],
    diagnostics: Optional[List[Dict[str, Any]]] = None,
) -> List[Any]:
    """Try a specific Camelot extraction strategy and record diagnostics on failure."""
    page_str = str(page_num + 1)  # Camelot uses 1-based page numbers
    try:
        tables = camelot_io.read_pdf(  # type: ignore[attr-defined]
            str(pdf_path),
            pages=page_str,
            flavor=strategy["flavor"],
            **strategy["params"],
        )
        print(f"DEBUG: Page {page_num+1} Strategy {strategy.get('name')} found {len(tables)} tables")
        return list(tables)  # type: ignore[call-arg, return-value]
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        logger.warning(
            f"Strategy '{strategy.get('name', 'unknown')}' failed on page {page_str}: {e}"
        )
        try:
            if diagnostics is not None:
                diagnostics.append(
                    make_event(
                        "05_table_extractor",
                        "warning",
                        "camelot_strategy_failed",
                        str(e),
                        {"page": page_num, "strategy": strategy.get("name")},
                    )
                )
        except Exception as exc:
            log_stage_error('05_table_extractor', exc, {'context': '05'})
            raise
            pass
        return []


def extract_table_image(
    pdf_doc: Any,
    page_num: int,
    bbox: Tuple[float, float, float, float],
    output_dir: Path,
    table_idx: int,
    diagnostics: Optional[list] = None,
    custom_name: Optional[str] = None,
) -> Optional[str]:
    """Extract table as image with padding."""
    try:
        page = pdf_doc[page_num]
        x1, y1, x2, y2 = bbox
        page_height = page.rect.height
        page_width = page.rect.width

        # Add vertical padding
        table_height = y2 - y1
        vpad = table_height * VERTICAL_PADDING_RATIO
        y1_padded = max(0, y1 - vpad)
        y2_padded = min(page_height, y2 + vpad)

        # Add horizontal padding
        table_width = x2 - x1
        hpad = table_width * HORIZONTAL_PADDING_RATIO
        x1_padded = max(0, x1 - hpad)
        x2_padded = min(page_width, x2 + hpad)

        # Convert to PyMuPDF coordinates (origin top-left)
        # Camelot's y2 is the 'top' (higher value), y1 is 'bottom' (lower value)
        # PyMuPDF's y0 is 'top' (lower value), y1 is 'bottom' (higher value)
        rect_y0 = page_height - y2_padded
        rect_y1 = page_height - y1_padded
        bbox_rect = fitz.Rect(x1_padded, rect_y0, x2_padded, rect_y1)

        # Render the cropped table and save without PIL roundtrip (faster, less memory)
        pix = page.get_pixmap(clip=bbox_rect, dpi=PYMUPDF_DPI)
        filename = custom_name or f"page_{page_num+1}_table_{table_idx+1}.png"
        img_path = output_dir / filename
        try:
            # Let PyMuPDF determine format from extension (PNG)
            pix.save(str(img_path))
        except Exception as exc:
            log_stage_error('05_table_extractor', exc, {'context': '05'})
            raise
            # Fallback to explicit PNG bytes
            with open(img_path, "wb") as f:
                f.write(pix.tobytes("png"))

        return str(img_path)
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        logger.error(f"Failed to extract table image: {e}")
        try:
            if diagnostics is not None:
                diagnostics.append(
                    make_event(
                        "05_table_extractor",
                        "error",
                        "image_extract_failed",
                        str(e),
                        {"page": page_num, "table_idx": table_idx},
                    )
                )
        except Exception as exc:
            log_stage_error('05_table_extractor', exc, {'context': '05'})
            raise
            pass
        return None


def extract_tables_from_page(
    pdf_path: Path,
    page_num: int,
    pdf_doc: Any,
    output_dir: Path,
    last_good_strategy: Optional[str] = None,
    diagnostics: Optional[list] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str], Dict[str, Any], Dict[str, Any]]:
    """Extract all tables from a single page using multiple strategies."""
    page_tables: Dict[tuple, Dict[str, Any]] = {}
    best_strategy = None
    page_metrics = {
        "retry_candidates": 0,
        "fallback_tables": 0,
        "fallback_applied": False,
    }

    # Strategy policy:
    # - Prefer the last strategy that succeeded on a prior page *iff* it is a lattice
    #   variant (avoid sticking to stream).
    # - Default to lattice(line_scale=15) on the first page.
    # - Only fall back to alternates when the page still "needs more" (no tables
    #   or high fragmentation).
    strategies_to_try = []
    baseline_name = "lattice_default"
    if last_good_strategy in CAMELOT_STRATEGIES:
        if CAMELOT_STRATEGIES[last_good_strategy]["flavor"] == "lattice":
            baseline_name = last_good_strategy
    strategies_to_try.append({"name": baseline_name, **CAMELOT_STRATEGIES[baseline_name]})
    fallback_strategies = []

    # Prioritize Lattice variants over Stream in fallback
    other_strategies = [k for k in CAMELOT_STRATEGIES.keys() if k != baseline_name]
    other_strategies.sort(key=lambda x: (0 if "lattice" in CAMELOT_STRATEGIES[x]["flavor"] else 1))

    for name in other_strategies:
        fallback_strategies.append({"name": name, **CAMELOT_STRATEGIES[name]})

    # Track per-strategy durations
    strategy_durations = {}
    fallback_applied_for_page = False

    def _bbox_tuple_for(table_obj: Any) -> Optional[tuple]:
        bt = getattr(table_obj, "_bbox", None)
        if not bt and hasattr(table_obj, "cells") and getattr(table_obj, "cells"):
            try:
                xs = [c.x1 for c in table_obj.cells] + [c.x2 for c in table_obj.cells]
                ys = [c.y1 for c in table_obj.cells] + [c.y2 for c in table_obj.cells]
                bt = (min(xs), min(ys), max(xs), max(ys))
            except Exception as exc:
                log_stage_error('05_table_extractor', exc, {'context': '05'})
                raise
                bt = None
        return bt

    def _iou(a: tuple, b: tuple) -> float:
        try:
            ax0, ay0, ax1, ay1 = a
            bx0, by0, bx1, by1 = b
            inter_w = max(0.0, min(ax1, bx1) - max(ax0, bx0))
            inter_h = max(0.0, min(ay1, by1) - max(ay0, by0))
            inter = inter_w * inter_h
            area_a = max(0.0, (ax1 - ax0)) * max(0.0, (ay1 - ay0))
            area_b = max(0.0, (bx1 - bx0)) * max(0.0, (by1 - by0))
            union = area_a + area_b - inter
            return float(inter / union) if union > 0 else 0.0
        except Exception as exc:
            log_stage_error('05_table_extractor', exc, {'context': '05'})
            raise
            return 0.0

    def _quantize_bbox(bt: tuple) -> tuple:
        return tuple(round(float(x), 2) for x in bt)

    def _register_table(
        strategy_name: str,
        table_obj: Any,
        bbox_key: tuple,
        score_val: float,
    ) -> Tuple[str, bool]:
        nonlocal fallback_applied_for_page, best_strategy

        new_frag = fragmentation_score(table_obj.df)
        history_entry = {
            "strategy": strategy_name,
            "fragmentation": new_frag,
            "score": score_val,
        }
        existing = page_tables.get(bbox_key)
        if existing is not None:
            existing_frag = int(existing.get("fragmentation", 0) or 0)
            existing_score = float(existing.get("score", 0.0) or 0.0)
            existing_strategy = existing.get("strategy", "")
            
            # Guard: Don't let stream replace lattice unless lattice is very poor
            # Stream often has 0 fragmentation (prose) but poor structure
            if "lattice" in existing_strategy and "stream" in strategy_name:
                # Only replace if lattice is effectively empty or extremely sparse
                if existing_score > 10 and existing_frag < 100:
                    return "skipped", bool(existing.get("quality_fallback", False))

            if not should_replace_table(existing_frag, new_frag, existing_score, score_val):
                return "skipped", bool(existing.get("quality_fallback", False))
            history = list(existing.get("history", []))
            history.append(history_entry)
            quality_fallback = bool(existing.get("quality_fallback", False))
            if strategy_name != existing.get("strategy") and (
                has_fragmentation_improvement(existing_frag, new_frag)
                or should_retry_fragmentation(existing_frag)
            ):
                quality_fallback = True
            page_tables[bbox_key] = {
                "table": table_obj,
                "score": score_val,
                "strategy": strategy_name,
                "fragmentation": new_frag,
                "history": history,
                "quality_fallback": quality_fallback,
            }
            if page_tables[bbox_key]["quality_fallback"]:
                fallback_applied_for_page = True
            best_strategy = strategy_name
            return "replaced", page_tables[bbox_key]["quality_fallback"]

        quality_fallback = strategy_name != baseline_name
        page_tables[bbox_key] = {
            "table": table_obj,
            "score": score_val,
            "strategy": strategy_name,
            "fragmentation": new_frag,
            "history": [history_entry],
            "quality_fallback": quality_fallback,
        }
        if quality_fallback:
            fallback_applied_for_page = True
        best_strategy = strategy_name
        return "added", quality_fallback

    # Try each strategy
    # First pass: baseline only
    for strategy in strategies_to_try:
        import time as _t

        _t0 = _t.monotonic()
        tables = try_camelot_strategy(pdf_path, page_num, strategy, diagnostics)
        _dt = int((_t.monotonic() - _t0) * 1000)
        nm = strategy.get("name")
        strategy_durations.setdefault(nm, {"count": 0, "total_ms": 0})
        strategy_durations[nm]["count"] += 1
        strategy_durations[nm]["total_ms"] += _dt

        found_count = 0

        for table in tables:
            bbox_tuple = _bbox_tuple_for(table)
            score = score_table(table.df)
            if score == 0:
                continue
            if not bbox_tuple:
                # if we cannot determine bbox, skip this table instance
                continue
            bbox_q = _quantize_bbox(bbox_tuple)

            replaced_existing_high_iou = False  # ensure flag is defined per table
            for existing_key in list(page_tables.keys()):
                iou = _iou(bbox_q, existing_key)
                print(
                    f"DEBUG: Comparing bbox_q={bbox_q} with existing_key={existing_key}. IOU={iou:.4f}",
                    file=sys.stderr,
                )
                if iou >= 0.70:
                    replaced_existing_high_iou = True
                    action, quality_flag = _register_table(
                        strategy["name"], table, existing_key, score
                    )
                    break  # Break after finding an overlapping existing table
            if not replaced_existing_high_iou:
                action, quality_flag = _register_table(
                    strategy["name"], table, bbox_q, score
                )
                if action in {"added", "replaced"}:
                    found_count += 1
                    if action == "replaced" and quality_flag:
                        strategy_durations[nm].setdefault("quality_upgrades", 0)
                        strategy_durations[nm]["quality_upgrades"] += 1

        # record per-page count for this strategy after processing
        strategy_durations[nm].setdefault("found", {})[page_num] = int(found_count)
        # If baseline found any tables with zero fragmentation, stop early
        if (
            strategy.get("name") == baseline_name
            and found_count > 0
            and any(
                info.get("fragmentation", 0) == 0 for info in page_tables.values()
            )
        ):
            break

    retry_keys = {
        key
        for key, info in page_tables.items()
        if should_retry_fragmentation(int(info.get("fragmentation", 0) or 0))
    }
    if retry_keys:
        page_metrics["retry_candidates"] = len(retry_keys)

    needs_more = not page_tables or bool(retry_keys)

    if needs_more:
        stop_after_first = not page_tables
        for strategy in fallback_strategies:
            import time as _t

            _t0 = _t.monotonic()
            tables = try_camelot_strategy(pdf_path, page_num, strategy, diagnostics)

            _dt = int((_t.monotonic() - _t0) * 1000)
            nm = strategy.get("name")
            strategy_durations.setdefault(nm, {"count": 0, "total_ms": 0})
            strategy_durations[nm]["count"] += 1
            strategy_durations[nm]["total_ms"] += _dt

            found_count = 0

            def _bbox_tuple_for(table_obj: Any) -> Optional[tuple]:
                bt = getattr(table_obj, "_bbox", None)
                if not bt and hasattr(table_obj, "cells") and getattr(table_obj, "cells"):
                    try:
                        xs = [c.x1 for c in table_obj.cells] + [c.x2 for c in table_obj.cells]
                        ys = [c.y1 for c in table_obj.cells] + [c.y2 for c in table_obj.cells]
                        bt = (min(xs), min(ys), max(xs), max(ys))
                    except Exception as exc:
                        log_stage_error('05_table_extractor', exc, {'context': '05'})
                        raise
                        bt = None
                return bt

            def _iou(a: tuple, b: tuple) -> float:
                try:
                    ax0, ay0, ax1, ay1 = a
                    bx0, by0, bx1, by1 = b
                    inter_w = max(0.0, min(ax1, bx1) - max(ax0, bx0))
                    inter_h = max(0.0, min(ay1, by1) - max(ay0, by0))
                    inter = inter_w * inter_h
                    area_a = max(0.0, (ax1 - ax0)) * max(0.0, (ay1 - ay0))
                    area_b = max(0.0, (bx1 - bx0)) * max(0.0, (by1 - by0))
                    union = area_a + area_b - inter
                    return float(inter / union) if union > 0 else 0.0
                except Exception as exc:
                    log_stage_error('05_table_extractor', exc, {'context': '05'})
                    raise
                    return 0.0

            def _quantize_bbox(bt: tuple) -> tuple:
                return tuple(round(float(x), 2) for x in bt)

            for table in tables:
                bbox_tuple = _bbox_tuple_for(table)
                score = score_table(table.df)
                if score == 0 or not bbox_tuple:
                    continue
                bbox_q = _quantize_bbox(bbox_tuple)
                
                replaced_existing_high_iou = False # Initialize here
                for existing_key in list(page_tables.keys()):
                    iou = _iou(bbox_q, existing_key)
                    if iou >= 0.70:
                        replaced_existing_high_iou = True
                        action, quality_flag = _register_table(
                            strategy["name"], table, existing_key, score
                        )
                        break
                if not replaced_existing_high_iou:
                    action, quality_flag = _register_table(
                        strategy["name"], table, bbox_q, score
                    )
                    if action in {"added", "replaced"}:
                        found_count += 1
                        if action == "replaced" and quality_flag:
                            strategy_durations[nm].setdefault("quality_upgrades", 0)
                            strategy_durations[nm]["quality_upgrades"] += 1

            strategy_durations[nm].setdefault("found", {})[page_num] = int(found_count)
            if stop_after_first and found_count > 0:
                if page_num == 4:
                     print(f"DEBUG: Page 5 would stop here (found {found_count} with {nm}), but continuing for debug.")
                else:
                     break

    page_metrics["fallback_applied"] = fallback_applied_for_page
    page_metrics["fallback_tables"] = sum(
        1 for info in page_tables.values() if info.get("quality_fallback")
    )

    # Convert to output format: KEEP ALL detected tables for this page.
    # Legacy single-best behavior is handled later via TABLE_SELECT_ONE_PER_PAGE gating.
    extracted_tables: List[Dict[str, Any]] = []
    if page_tables:
        idx = 0
        for bbox_key, table_info in page_tables.items():
            table = table_info["table"]
            # Extract bbox
            bbox_tuple = getattr(table, "_bbox", None)
            if not bbox_tuple and hasattr(table, "cells") and getattr(table, "cells"):
                try:
                    xs = [c.x1 for c in table.cells] + [c.x2 for c in table.cells]
                    ys = [c.y1 for c in table.cells] + [c.y2 for c in table.cells]
                    bbox_tuple = (min(xs), min(ys), max(xs), max(ys))
                except Exception as exc:
                    log_stage_error('05_table_extractor', exc, {'context': '05'})
                    raise
                    bbox_tuple = None
            # Optionally extract an image per table
            img_path = (
                extract_table_image(pdf_doc, page_num, bbox_tuple, output_dir, idx, diagnostics)
                if bbox_tuple
                else None
            )
            # Optional header coalesce before metrics
            df = table.df
            if TABLE_HEADER_COALESCE_ENABLED:
                try:
                    df = coalesce_repeated_header_rows(df, TABLE_HEADER_REPEAT_MIN_MATCH)
                except Exception as exc:
                    log_stage_error('05_table_extractor', exc, {'context': '05'})
                    raise
                    logger.debug("Header coalesce failed; continuing")
                    try:
                        diagnostics.append(
                            make_event(
                                "05_table_extractor",
                                "warning",
                                "header_coalesce_failed",
                                str(e),
                                {"page_index": page_num, "table_idx": idx},
                            )
                        )
                    except Exception as exc:
                        log_stage_error('05_table_extractor', exc, {'context': '05'})
                        raise
                        pass
            df_clean = df.map(sanitize_cell)
            fragmentation = fragmentation_score(df_clean)
            table_data = {
                "page_number": page_num + 1,
                "page_index": page_num,
                "table_index": idx + 1,
                "bbox": list(bbox_tuple) if bbox_tuple else [],
                "extraction_method": "camelot",
                "strategy": table_info["strategy"],
                "fragmentation_score": fragmentation,
                "pandas_df_raw": df.to_dict("records"),
                "pandas_df": df_clean.to_dict("records"),
                "pandas_metrics": generate_pandas_metrics(df_clean),
                "camelot_metrics": {
                    "accuracy": getattr(table, "accuracy", None),
                    "whitespace": getattr(table, "whitespace", None),
                    "order": getattr(table, "order", None),
                },
                "score": table_info.get("score", 0.0),
                "quality_fallback": bool(table_info.get("quality_fallback", False)),
                "strategy_history": table_info.get("history", []),
            }
            if img_path:
                try:
                    table_data["table_image_path"] = str(
                        Path(img_path).resolve().relative_to(output_dir.parent.parent.resolve())
                    )
                except Exception as exc:
                    log_stage_error('05_table_extractor', exc, {'context': '05'})
                    raise
                    table_data["table_image_path"] = img_path
            extracted_tables.append(table_data)
            idx += 1

    return extracted_tables, best_strategy, strategy_durations, page_metrics


## moved to utils: _normalize_cell


## moved to utils: coalesce_repeated_header_rows


def extract_all_tables(
    pdf_path: Path, output_dir: Path, diagnostics: Optional[list] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    """Extract all tables from a PDF."""
    all_tables: List[Dict[str, Any]] = []
    last_good_strategy = None
    strategy_summary: Dict[str, Dict[str, Any]] = {}
    quality_summary = {
        "pages_processed": 0,
        "pages_with_tables": 0,
        "pages_with_fallback": 0,
        "tables_with_fallback": 0,
        "retry_candidates": 0,
    }

    # Open PDF with PyMuPDF for image extraction
    try:
        pdf_doc = fitz.open(str(pdf_path))
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        logger.error(f"Failed to open PDF {pdf_path}: {e}")
        return [], {}, {}

    try:
        total_pages = len(pdf_doc)
        console.print(f"[cyan]Processing {total_pages} pages...[/cyan]")

        for page_num in range(total_pages):
            logger.info(f"Processing page {page_num + 1}/{total_pages}")

            tables, best_strategy, sdurs, page_metrics = extract_tables_from_page(
                pdf_path, page_num, pdf_doc, output_dir, last_good_strategy, diagnostics
            )

            quality_summary["pages_processed"] += 1
            if tables:
                quality_summary["pages_with_tables"] += 1
            if page_metrics.get("fallback_applied"):
                quality_summary["pages_with_fallback"] += 1
            quality_summary["tables_with_fallback"] += int(
                page_metrics.get("fallback_tables", 0) or 0
            )
            quality_summary["retry_candidates"] += int(
                page_metrics.get("retry_candidates", 0) or 0
            )

            if tables:
                all_tables.extend(tables)
            try:
                for k, v in sdurs.items():
                    entry = strategy_summary.setdefault(
                        k,
                        {
                            "attempts": 0,
                            "successes": 0,
                            "failures": 0,
                            "total_duration_ms": 0,
                            "per_page_ms": {},
                        },
                    )
                    cnt = int(v.get("count", 0) or 0)
                    entry["attempts"] += cnt
                    # Mark success if found>0 for this page
                    found_map = v.get("found") or {}
                    if isinstance(found_map, dict) and int(found_map.get(page_num, 0) or 0) > 0:
                        entry["successes"] += 1
                    else:
                        entry["failures"] += 1
                    dur = int(v.get("total_ms", 0) or 0)
                    entry["total_duration_ms"] += dur
                    # Approximate per_page_ms as average duration per attempt for this page
                    per_attempt = int(dur / max(1, cnt)) if cnt else dur
                    entry["per_page_ms"][str(page_num)] = per_attempt
            except Exception as exc:
                log_stage_error('05_table_extractor', exc, {'context': '05'})
                raise
                # Per-page strategy timing aggregation failed; continue.
                pass
            # Record last good strategy outside the exception path so it updates on success.
            if best_strategy:
                last_good_strategy = best_strategy

            console.print(f"  Page {page_num + 1}: Found {len(tables)} tables")

    finally:
        pdf_doc.close()

    # Final regression guard: de-dupe high-IOU overlaps per page (safety net)
    def _iou(a: List[float], b: List[float]) -> float:
        try:
            ax0, ay0, ax1, ay1 = a
            bx0, by0, bx1, by1 = b
            inter_w = max(0.0, min(ax1, bx1) - max(ax0, bx0))
            inter_h = max(0.0, min(ay1, by1) - max(ay0, by0))
            inter = inter_w * inter_h
            area_a = max(0.0, (ax1 - ax0)) * max(0.0, (ay1 - ay0))
            area_b = max(0.0, (bx1 - bx0)) * max(0.0, (by1 - by0))
            union = area_a + area_b - inter
            return float(inter / union) if union > 0 else 0.0
        except Exception as exc:
            log_stage_error('05_table_extractor', exc, {'context': '05'})
            raise
            return 0.0

    deduped: List[Dict[str, Any]] = []
    by_page: Dict[int, List[Dict[str, Any]]] = {}
    for t in all_tables:
        by_page.setdefault(int(t.get("page_index", t.get("page_number", 0)) or 0), []).append(t)

    for page, tables in by_page.items():
        kept: List[Dict[str, Any]] = []
        for t in tables:
            bbox = t.get("bbox") or []
            if len(bbox) != 4:
                kept.append(t)
                continue
            overlap = False
            for k in kept:
                kbbox = k.get("bbox") or []
                if len(kbbox) != 4:
                    continue
                if _iou(bbox, kbbox) >= 0.70:
                    overlap = True
                    # Keep higher-score table
                    if float(t.get("score", 0) or 0.0) > float(k.get("score", 0) or 0.0):
                        k.update(t)
                    break
            if not overlap:
                kept.append(t)
        deduped.extend(kept)

    if len(deduped) < len(all_tables):
        logger.info(
            f"05_table_extractor: de-duped high-IOU overlaps "
            f"({len(all_tables)} → {len(deduped)})"
        )

    return deduped, strategy_summary, quality_summary


def run(
    input_json: Path,
    pdf_dir: Path = Path("data/results/pipeline/01_annotation_processor"),
    output_dir: Path = Path("data/results/pipeline"),
):
    """Extracts tables from the PDF and associates them with sections."""
    console.print(f"[green]Extracting tables based on sections in: {input_json.name}[/green]")
    # Configure a stage-specific log file for debugging
    try:
        stage_output_dir = output_dir / "05_table_extractor"
        stage_output_dir.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(stage_output_dir / "stage_05_table_extractor.log"),
            level="INFO",
            enqueue=True,
            backtrace=False,
            diagnose=False,
            rotation="1 week",
            retention="14 days",
        )
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        pass
    # Fail fast when any SciLLM-powered feature is enabled (split/confirm/assist)
    def _env_true(name: str, default: str = "0") -> bool:
        return os.getenv(name, default).lower() in {"1", "true", "yes", "y"}

    llm_features_enabled = (
        _env_true("STAGE05_LLM_SPLIT_1COL", "1")
        or _env_true("STAGE05_LLM_CONFIRM_LOWCONF", "1")
        or _env_true("TABLE_LLM_ASSIST", "0")
    )
    # SciLLM preflight is handled centrally by run_pipeline for online runs.
    # Here we assume any required preflight has already passed; for offline
    # flows (e.g. summary-only + skip-fig-descriptions) llm_features_enabled
    # can still be true, but we avoid forcing a hard dependency so the
    # deterministic parts of Stage 05 remain usable.
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
                    "05_table_extractor",
                    "info",
                    "gpu_metrics_unavailable",
                    "NVML not available; GPU metrics disabled",
                    {},
                )
            )
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        pass

    # --- Input Validation ---
    if not input_json.exists():
        raise FileNotFoundError(f"Input JSON not found: {input_json}")

    with open(input_json, "r") as f:
        sections_data = json.load(f)
    # Prefer an explicit source PDF recorded by the upstream stage
    clean_pdf = sections_data.get("source_pdf") or sections_data.get("clean_pdf")
    if clean_pdf:
        pdf_path = Path(clean_pdf)
    else:
        try:
            pdf_path = next(pdf_dir.glob("*_clean.pdf"))
        except StopIteration:
            raise FileNotFoundError(f"No '*_clean.pdf' found in pdf_dir: {pdf_dir}")
    sections = sections_data.get("sections", [])

    # --- Directory Setup ---
    stage_output_dir = output_dir / "05_table_extractor"
    json_output_dir = stage_output_dir / "json_output"
    image_output_dir = stage_output_dir / "image_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)
    image_output_dir.mkdir(exist_ok=True)

    # --- Table Extraction ---
    all_tables, strategy_summary, quality_summary = extract_all_tables(
        pdf_path, image_output_dir, diagnostics
    )

    # --- Filter out single-column tables that match section headers (stage 04 already handled them) ---
    section_titles = set()
    for section in sections:
        title = section.get("title", "").strip()
        if title:
            # Normalize: remove extra whitespace, lowercase for comparison
            normalized = " ".join(title.split()).lower()
            section_titles.add(normalized)
    
    if section_titles:
        def _is_section_header_table(table: dict) -> bool:
            pm = table.get("pandas_metrics", {}) or {}
            shape = pm.get("shape", [0, 0])
            cols = int(shape[1]) if isinstance(shape, (list, tuple)) and len(shape) > 1 else 0
            # Only check single-column tables
            if cols != 1:
                return False
            # Extract text from all cells
            df_data = table.get("pandas_df", [])
            if not df_data:
                return False
            # Concatenate all cell text
            table_text_parts = []
            for row in df_data:
                if isinstance(row, dict):
                    for val in row.values():
                        table_text_parts.append(str(val).strip())
                elif isinstance(row, list):
                    for val in row:
                        table_text_parts.append(str(val).strip())
            table_text = " ".join(table_text_parts)
            normalized_table = " ".join(table_text.split()).lower()
            # Check if it fuzzy-matches any section header (98% threshold to handle OCR errors)
            try:
                from rapidfuzz import fuzz
                for section_title in section_titles:
                    ratio = fuzz.ratio(normalized_table, section_title)
                    if ratio >= 98:
                        return True
                return False
            except ImportError:
                # Fallback to exact match if rapidfuzz not available
                return normalized_table in section_titles
        
        before_count = len(all_tables)
        all_tables = [t for t in all_tables if not _is_section_header_table(t)]
        removed = before_count - len(all_tables)
        if removed > 0:
            try:
                diagnostics.append(make_event("05_table_extractor", "info", "filtered_section_headers", f"Removed {removed} single-column tables matching section headers", {"count": removed}))
            except Exception as exc:
                log_stage_error('05_table_extractor', exc, {'context': '05'})
                raise
                pass

    # --- Repair: reconstruct collapsed single-column header rows (page header-only tables)
    # Some PDFs cause Camelot to collapse a 1-row, multi-column header into a single text cell.
    # We attempt a deterministic reconstruction via PDF word spans; optionally reinforce with an LLM split.
    def _reconstruct_single_col_header(table: Dict[str, Any]) -> bool:
        try:
            pm = table.get("pandas_metrics") or {}
            shape = pm.get("shape") or [0, 0]
            rows = int(shape[0] or 0)
            cols = int(shape[1] or 0)
            if rows != 1 or cols != 1:
                return False
            bbox = table.get("bbox") or []
            if not bbox:
                return False
            import re as _re
            import fitz as _fitz
            page_idx = int(table.get("page_index", 0) or 0)
            with _fitz.open(str(pdf_path)) as _doc:
                _page = _doc[page_idx]
                x0, y0, x1, y1 = bbox
                # Convert Camelot coords (origin bottom-left) to PyMuPDF rect (origin top-left)
                # page height reference
                _H = _page.rect.height
                rect = _fitz.Rect(x0, _H - y1, x1, _H - y0)
                words = _page.get_text("words", clip=rect) or []  # (x0,y0,x1,y1,word,block_no,line_no,word_no)
                words = [w for w in words if (w[4] or "").strip()]
                if not words:
                    return False
                # First try robust whitespace/pipes split from the original single cell text
                try:
                    src_df = pd.DataFrame(table.get("pandas_df") or [])
                    raw_txt = ""
                    if not src_df.empty:
                        raw_txt = str(list(src_df.iloc[0].values)[0])
                    tokens_ws = [t.strip() for t in _re.split(r"\s{2,}|\s\|\s|\t+", raw_txt) if t.strip()]
                except Exception as exc:
                    log_stage_error('05_table_extractor', exc, {'context': '05'})
                    raise
                    tokens_ws = []
                # Columnize by X clusters as fallback/primary
                words_sorted = sorted(words, key=lambda w: (float(w[0]), float(w[1])))
                cols_spans: list[list[tuple[float, float, str]]] = []
                GAP_MIN = 10.0  # points
                cur: list[tuple[float, float, str]] = []
                prev_x1 = None
                for (wx0, wy0, wx1, wy1, wtxt, *_rest) in words_sorted:
                    if prev_x1 is None:
                        cur = [(wx0, wx1, wtxt)]
                        prev_x1 = wx1
                        continue
                    if (wx0 - prev_x1) >= GAP_MIN:
                        if cur:
                            cols_spans.append(cur)
                        cur = [(wx0, wx1, wtxt)]
                    else:
                        cur.append((wx0, wx1, wtxt))
                    prev_x1 = max(prev_x1, wx1) if prev_x1 is not None else wx1
                if cur:
                    cols_spans.append(cur)
                # Normalize columns text
                col_texts = [" ".join([t[2] for t in col]).strip() for col in cols_spans]
                # Pick best between whitespace split and spatial split
                candidates = [tokens_ws, col_texts]
                best = max(candidates, key=lambda L: len(L or []))
                best = [sanitize_cell(t) for t in (best or []) if t]
                # Guardrails: require 3–10 columns to accept; else bail to LLM path
                if len(best) < 3:
                    return False
                # Build a 1xN dataframe so metrics reflect proper column count
                try:
                    df = pd.DataFrame([best], columns=best)
                except Exception as exc:
                    log_stage_error('05_table_extractor', exc, {'context': '05'})
                    raise
                    # If duplicate names, uniquify
                    uniq: list[str] = []
                    seen = set()
                    for h in best:
                        hh = h
                        k = 1
                        while hh in seen:
                            k += 1
                            hh = f"{h}_{k}"
                        uniq.append(hh)
                        seen.add(hh)
                    df = pd.DataFrame([uniq], columns=uniq)
                # Do not mutate Camelot DataFrame; record inferred headers as metadata only
                table["header_inferred"] = best
                table["header_provenance"] = "spatial"
                return True
        except Exception as exc:
            log_stage_error('05_table_extractor', exc, {'context': '05'})
            raise
            return False

    def _llm_split_single_col_header(table: Dict[str, Any]) -> bool:
        """Use SciLLM to split a single-cell header into multiple column names.
        Returns True if table was updated.
        """
        try:
            if os.getenv("STAGE05_LLM_SPLIT_1COL", "1").lower() not in {"1","true","yes","y"}:
                return False
            if not quick_scillm_check():
                return False
            pm = table.get("pandas_metrics") or {}
            shp = pm.get("shape") or [0, 0]
            rows = int(shp[0] or 0); cols = int(shp[1] or 0)
            if rows != 1 or cols != 1:
                return False
            # Extract the lone cell text
            src_df = pd.DataFrame(table.get("pandas_df") or [])
            if src_df.empty:
                return False
            cell_text = str(list(src_df.iloc[0].values)[0]).strip()
            if not cell_text:
                return False
            import asyncio as _asyncio
            async def _call():
                router = get_text_router()
                system = (
                    "You split a single table header cell into distinct column names.\n"
                    "Return strict JSON: {\"columns\":[\"...\"]}.\n"
                    "Do not invent domain-specific terms beyond the text."
                )
                user = json.dumps({"header_text": cell_text}, ensure_ascii=False)
                resp = await router.acompletion(
                    model="chutes/text",
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": [{"type": "text", "text": user}]},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0,
                    max_tokens=256,
                    timeout=int(os.getenv("SC_TIMEOUT_STAGE_05_SPLIT_1COL", "20")),
                )
                return resp
            resp = _asyncio.run(_call())
            content = getattr(resp, "choices", [{}])[0].get("message", {}).get("content", "")
            cols_out: list[str] = []
            try:
                data = json.loads(content) if isinstance(content, str) else content
                cols_out = [sanitize_cell(c) for c in (data.get("columns") or []) if c]
            except Exception as exc:
                log_stage_error('05_table_extractor', exc, {'context': '05'})
                raise
                cols_out = []
            if len(cols_out) < 3:
                return False
            # Update table with the split columns
            try:
                df = pd.DataFrame([cols_out], columns=cols_out)
            except Exception as exc:
                log_stage_error('05_table_extractor', exc, {'context': '05'})
                raise
                df = pd.DataFrame([cols_out])
            # Do not mutate Camelot DataFrame; record inferred headers as metadata only
            table["header_inferred"] = cols_out
            table["header_provenance"] = "llm"
            recorded_model = os.getenv("CHUTES_TEXT_MODEL") or "chutes/text"
            table["llm_assist"] = {"model": recorded_model, "patch": {"split_1col": True}}
            log_timing(
                "05_table_extractor",
                {"attempt": "llm_split_1col", "outcome": "ok", "table_hash": _stable_table_hash(table)},
                stage_dir=stage_output_dir,
            )
            return True
        except Exception as exc:
            log_stage_error('05_table_extractor', exc, {'context': '05'})
            raise
            log_timing(
                "05_table_extractor",
                {"attempt": "llm_split_1col", "outcome": "error", "error": str(e)},
                stage_dir=stage_output_dir,
            )
            return False

    # Apply reconstruction, then LLM split for any 1-column header-only table
    repaired = 0
    for t in all_tables:
        fixed = _reconstruct_single_col_header(t)
        if not fixed:
            fixed = _llm_split_single_col_header(t)
        if fixed:
            repaired += 1
    if repaired:
        try:
            diagnostics.append(make_event("05_table_extractor", "info", "single_col_repairs", f"Repaired {repaired} tables", {"count": repaired}))
        except Exception as exc:
            log_stage_error('05_table_extractor', exc, {'context': '05'})
            raise
            pass

    # --- Heuristic merge: stitch header-only tables with body tables across pages
    def is_header_row_table(t: Dict[str, Any]) -> bool:
        """Keyword-agnostic heuristic for header-only tables.

        Criteria:
        - Exactly 1 row and at least 2 columns.
        - Average cell length not too large (<= 32 chars).
        - Combined digit ratio across cells < 0.5 (header cells tend to be mostly alphabetic).
        """
        metrics = t.get("pandas_metrics", {}) or {}
        shape = metrics.get("shape", [0, 0])
        rows = int(shape[0]) if isinstance(shape, (list, tuple)) and shape else 0
        cols = int(shape[1]) if isinstance(shape, (list, tuple)) and shape else 0
        if rows != 1 or cols < 2:
            return False
        try:
            first = (t.get("pandas_df") or [{}])[0]
            # Preserving order by numeric key, else arbitrary
            keys = sorted(first.keys(), key=lambda k: int(str(k)) if str(k).isdigit() else 9999)
            values = [str(first[k]).strip() for k in keys]
            if not values:
                return False
            avg_len = sum(len(v) for v in values) / max(1, len(values))
            digits = sum(sum(ch.isdigit() for ch in v) for v in values)
            total = sum(len(v) for v in values) or 1
            digit_ratio = digits / total
            return (avg_len <= 32) and (digit_ratio < 0.5)
        except Exception as exc:
            log_stage_error('05_table_extractor', exc, {'context': '05'})
            raise
            return False

    def horizontal_iou(a: List[float], b: List[float]) -> float:
        try:
            ax0, _, ax1, _ = a
            bx0, _, bx1, _ = b
            inter = max(0.0, min(ax1, bx1) - max(ax0, bx0))
            uni = max(ax1, bx1) - min(ax0, bx0)
            return float(inter / uni) if uni > 0 else 0.0
        except Exception as exc:
            log_stage_error('05_table_extractor', exc, {'context': '05'})
            raise
            return 0.0

    def stitch_headers(tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not tables:
            return tables
        # Index candidates by page
        by_page: Dict[int, List[Dict[str, Any]]] = {}
        for t in tables:
            by_page.setdefault(int(t.get("page_index", 0)), []).append(t)

        used_headers: set[int] = set()
        stitched: List[Dict[str, Any]] = []
        for t in tables:
            # Skip header-only tables that will be stitched
            if is_header_row_table(t):
                page = int(t.get("page_index", 0))
                bbox = t.get("bbox", [])
                cols = int((t.get("pandas_metrics", {}) or {}).get("shape", [0, 0])[1] or 0)
                header_idx = id(t)
                # Search body on same or next page
                candidate_pages = [page]
                if TABLE_STITCH_ALLOW_NEXT_PAGE:
                    candidate_pages.append(page + 1)
                candidates = []
                for p in candidate_pages:
                    candidates.extend(by_page.get(p, []) or [])
                best = None
                best_score = -1.0
                for c in candidates:
                    if c is t:
                        continue
                    m = c.get("pandas_metrics", {}) or {}
                    shape = m.get("shape", [0, 0])
                    rows_c = int(shape[0]) if isinstance(shape, (list, tuple)) and shape else 0
                    cols_c = int(shape[1]) if isinstance(shape, (list, tuple)) and shape else 0
                    if rows_c < 2 or cols_c != cols:
                        continue
                    iou = horizontal_iou(bbox, c.get("bbox", []))
                    if iou < TABLE_STITCH_MIN_HORIZONTAL_IOU:
                        continue
                    score = float(c.get("score", 0.0)) + iou
                    if score > best_score:
                        best_score = score
                        best = c
                if best is not None:
                    # Apply header row as column names for 'best'
                    try:
                        import pandas as pd

                        header_row = (t.get("pandas_df") or [{}])[0]
                        keys = sorted(
                            header_row.keys(),
                            key=lambda k: int(str(k)) if str(k).isdigit() else 9999,
                        )
                        new_cols = [
                            str(header_row[k]).strip() or str(i) for i, k in enumerate(keys)
                        ]
                        body_df = pd.DataFrame(best.get("pandas_df") or [])
                        if len(body_df.columns) == len(new_cols):
                            body_df.columns = new_cols
                            # Update best table payload and metrics
                            best["pandas_df"] = body_df.to_dict("records")
                            best["pandas_metrics"] = generate_pandas_metrics(body_df)
                            used_headers.add(header_idx)
                    except Exception as exc:
                        log_stage_error('05_table_extractor', exc, {'context': '05'})
                        raise
                        pass
                # Don't append header-only table; it will be dropped by filters anyway
                continue
            stitched.append(t)
        return stitched

    
    # --- Caption detection: scan PDF text just above the table for captions like "Table 4-1. ..."
    def detect_table_caption(pdf_path: Path, page_index: int, bbox: List[float]) -> str | None:
        """Find a nearby caption/title for a table.

        Strategy:
        1) Scan a narrow band just above the table.
        2) If not found, scan a wider band.
        3) As a last resort, scan all text blocks above y0 on the page.
        """
        try:
            doc = fitz.open(str(pdf_path))
            page = doc[page_index]
            rect = fitz.Rect(*bbox)
            def _scan_band(top: float) -> str | None:
                band = fitz.Rect(rect.x0, max(0, top), rect.x1, rect.y0)
                blocks = page.get_text('blocks', clip=band)
                blocks = sorted(blocks, key=lambda b: -b[1])  # y desc
                for b in blocks:
                    txt = (b[4] or '').strip()
                    if not txt:
                        continue
                    if re.match(r"^\s*Table\s+\d+(?:[-–]\d+)?[.:]", txt, re.IGNORECASE):
                        return txt
                return None
            # narrow (80pt) then wider (200pt)
            cap = _scan_band(max(0, rect.y0 - 80))
            if cap:
                return cap
            cap = _scan_band(max(0, rect.y0 - 200))
            if cap:
                return cap
            # Fallback: any block above y0 on the page
            blocks = page.get_text('blocks')
            above = [b for b in blocks if b[3] <= rect.y0]  # block bottom is b[3]
            above = sorted(above, key=lambda b: -b[1])
            for b in above:
                txt = (b[4] or '').strip()
                if not txt:
                    continue
                if re.match(r"^\s*Table\s+\d+(?:[-–]\d+)?[.:]", txt, re.IGNORECASE):
                    return txt
            return None
        except Exception as exc:
            log_stage_error('05_table_extractor', exc, {'context': '05'})
            raise
            return None

    if TABLE_HEADER_STITCHING_ENABLED:
        all_tables = stitch_headers(all_tables)

    # --- Associate Tables with Sections ---
    for table in all_tables:
        table_bbox = fitz.Rect(table["bbox"])
        for section in sections:
            section_bbox = fitz.Rect(section["bbox"])
            if section["page_start"] <= table["page_index"] <= section["page_end"]:
                if section_bbox.intersects(table_bbox):
                    table["section_id"] = section.get("id", f"sec_{sections.index(section)}")
                    break

    # Fallback association: if a table is still unassigned, link it to the nearest
    # preceding section on the same page (by Y), else the most recent section on earlier pages.
    unassigned = [t for t in all_tables if not t.get("section_id")]
    if unassigned:
        anchors = []
        for idx, s in enumerate(sections):
            try:
                y0 = float((s.get("bbox") or [0, 0, 0, 0])[1])
            except Exception as exc:
                log_stage_error('05_table_extractor', exc, {'context': '05'})
                raise
                y0 = 0.0
            anchors.append({
                "idx": idx,
                "page": int(s.get("page_start", 0)),
                "y0": y0,
                "id": s.get("id", f"sec_{idx}"),
                "title": s.get("title") or "",
            })
        for t in unassigned:
            p = int(t.get("page_index", 0))
            try:
                ty = float((t.get("bbox") or [0, 0, 0, 0])[1])
            except Exception as exc:
                log_stage_error('05_table_extractor', exc, {'context': '05'})
                raise
                ty = 0.0
            # same-page candidates with header above the table
            same = [a for a in anchors if a["page"] == p and a["y0"] <= ty]
            pick = None
            if same:
                pick = sorted(same, key=lambda a: a["y0"])[-1]
            else:
                # pick the most recent section on earlier pages
                prior = [a for a in anchors if a["page"] < p]
                if prior:
                    pick = sorted(prior, key=lambda a: (a["page"], a["y0"]))[-1]
            if pick:
                t["section_id"] = pick["id"]

    # Heuristic filtering: accept solid multi-row tables; allow header-only tables with reconstructed multi-columns
    # Optional LLM confirmation for low-confidence/empty DataFrames
    def _llm_confirm_is_table(t: Dict[str, Any]) -> bool | None:
        if os.getenv("STAGE05_LLM_CONFIRM_LOWCONF", "1").lower() not in {"1","true","yes","y"}:
            return None
        if not quick_scillm_check():
            return None
        pm = t.get("pandas_metrics") or {}
        cm = t.get("camelot_metrics") or {}
        src = t.get("pandas_df") or []
        rows_preview: list[list[str]] = []
        if isinstance(src, list):
            for r in src[:3]:
                if isinstance(r, dict):
                    rows_preview.append([str(v) for v in list(r.values())[:8]])
                elif isinstance(r, list):
                    rows_preview.append([str(v) for v in r[:8]])
        payload = {
            "rows_preview": rows_preview,
            "metrics": {
                "shape": pm.get("shape"),
                "density": pm.get("data_density"),
                "camelot_accuracy": cm.get("accuracy"),
                "fragmentation": t.get("fragmentation_score"),
            },
        }
        import asyncio as _asyncio
        async def _call():
            router = get_text_router()
            import json as _json
            system = (
                "You are a strict classifier for tabular vs non-tabular content.\n"
                "Return ONLY JSON: {\"is_table\": true|false}.\n"
                "If content looks like prose or lacks column structure, return false."
            )
            return await router.acompletion(
                model="chutes/text",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": [{"type": "text", "text": _json.dumps(payload, ensure_ascii=False)}]},
                ],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=40,
                timeout=int(os.getenv("SC_TIMEOUT_STAGE_05_CONFIRM", "12")),
            )
        try:
            resp = _asyncio.run(_call())
            content = getattr(resp, "choices", [{}])[0].get("message", {}).get("content", "")
            import json as _json
            data = _json.loads(content) if isinstance(content, str) else content
            val = data.get("is_table")
            return bool(val) if isinstance(val, bool) else None
        except Exception as exc:
            log_stage_error('05_table_extractor', exc, {'context': '05'})
            raise
            return None

    demoted_llm: list[dict[str, Any]] = []
    filtered_tables = []
    for t in all_tables:
        metrics = t.get("pandas_metrics", {}) or {}
        shape = metrics.get("shape", [0, 0])
        rows = int(shape[0]) if isinstance(shape, (list, tuple)) and shape else 0
        cols = int(shape[1]) if isinstance(shape, (list, tuple)) and shape else 0
        density = float(metrics.get("data_density", 0.0) or 0.0)
        try:
            acc = float((t.get("camelot_metrics") or {}).get("accuracy") or 0.0)
        except Exception as exc:
            log_stage_error('05_table_extractor', exc, {'context': '05'})
            raise
            acc = 0.0

        # If Camelot couldn't form a DF or confidence is low, confirm via LLM (live only)
        is_empty_df = (rows == 0 or cols == 0)
        very_sparse = (rows * cols <= 3 and density < 0.2)
        low_acc = (acc and acc < float(os.getenv("STAGE05_CAMELOT_ACC_MIN", "60")))
        if is_empty_df or very_sparse or low_acc:
            verdict = _llm_confirm_is_table(t)
            if verdict is False:
                try:
                    demoted_llm.append({
                        "page_idx": int(t.get("page_index", 0) or 0),
                        "bbox": t.get("bbox") or [],
                        "text": _extract_table_text_for_heuristics(t),
                        "reason": "llm_not_table",
                    })
                except Exception as exc:
                    log_stage_error('05_table_extractor', exc, {'context': '05'})
                    raise
                    pass
                try:
                    diagnostics.append(
                        make_event("05_table_extractor", "info", "llm_demote_not_table", "Demoted by LLM confirm", {
                            "rows": rows, "cols": cols, "density": density, "acc": acc
                        })
                    )
                except Exception as exc:
                    log_stage_error('05_table_extractor', exc, {'context': '05'})
                    raise
                    pass
                continue
        # Reject tables with suspiciously large bboxes (stream strategy false positives)
        # Standard US Letter page is 612x792 points
        try:
            import fitz as _fitz
            bbox_rect = _fitz.Rect(t.get("bbox", []))
            bbox_area = bbox_rect.width * bbox_rect.height
            # Reject if bbox covers >90% of standard page (612x792 = 484704)
            if bbox_area > 0.9 * 612 * 792:
                try:
                    diagnostics.append(
                        make_event("05_table_extractor", "warning", "table_bbox_too_large",
                                   f"Rejected table with suspiciously large bbox (area={bbox_area:.0f})",
                                   {"bbox": t.get("bbox"), "page": t.get("page_index")})
                    )
                except Exception as exc:
                    log_stage_error('05_table_extractor', exc, {'context': '05'})
                    raise
                    pass
                continue
        except Exception as exc:
            log_stage_error('05_table_extractor', exc, {'context': '05'})
            raise
            pass

        # Accept dense multi-row tables with at least 2 columns (single-column = prose/headers, not tabular data).
        # Additionally, retain 1-row header-only tables when they have >=3 columns so downstream can merge with body.
        if cols >= 2 and ((rows >= TABLE_FILTER_MIN_ROWS) or (rows >= 2 and density >= TABLE_FILTER_MIN_DENSITY) or (rows == 1 and cols >= 3)):
            filtered_tables.append(t)
        else:
            try:
                diagnostics.append(
                    make_event(
                        "05_table_extractor",
                        "warning",
                        "table_low_confidence",
                        "Filtered out low-confidence table",
                        {
                            "rows": rows,
                            "cols": cols,
                            "density": density,
                            "page": t.get("page_index"),
                            "strategy": t.get("strategy"),
                        },
                    )
                )
            except Exception as exc:
                log_stage_error('05_table_extractor', exc, {'context': '05'})
                raise
                pass

    # Selection behavior:
    # By default KEEP ALL filtered tables (no data loss).
    # If TABLE_SELECT_ONE_PER_PAGE=true, keep legacy behavior (exactly one per page).
    if TABLE_SELECT_ONE_PER_PAGE and all_tables:
        by_page: Dict[int, List[Dict[str, Any]]] = {}
        for t in all_tables:
            by_page.setdefault(int(t.get("page_index", 0)), []).append(t)
        selected: List[Dict[str, Any]] = []
        for page, candidates in sorted(by_page.items()):
            # Prefer strong tables (multi-row, dense)
            strong: List[Dict[str, Any]] = []
            for t in candidates:
                m = t.get("pandas_metrics", {}) or {}
                shape = m.get("shape", [0, 0])
                rows = int(shape[0]) if isinstance(shape, (list, tuple)) and shape else 0
                density = float(m.get("data_density", 0.0) or 0.0)
                if (rows >= TABLE_FILTER_MIN_ROWS) or (
                    rows >= 2 and density >= TABLE_FILTER_MIN_DENSITY
                ):
                    strong.append(t)
            try:
                best_list = strong if strong else candidates
                best = max(best_list, key=lambda t: float(t.get("score", 0.0)))
                selected.append(best)
            except Exception as exc:
                log_stage_error('05_table_extractor', exc, {'context': '05'})
                raise
                continue
        filtered_tables = selected

    # --- Assign captions/titles from nearby text if missing ---
    import re as _re
    import hashlib
    def _parse_table_label(txt: str) -> tuple[object, str]:
        # Returns (number, normalized_title_without_label)
        m = _re.match(r"\s*(?:Table|Tbl\.)\s*([A-Za-z0-9\-\.]+)?[\.:]?\s*(.*)$", txt, _re.IGNORECASE)
        if not m:
            return None, txt.strip()
        num = (m.group(1) or "").strip() or None
        rem = (m.group(2) or "").strip()
        return num, rem

    def _slug(s: str) -> str:
        s2 = "".join(ch.lower() if ch.isalnum() else "-" for ch in s)
        s2 = _re.sub(r"-+", "-", s2).strip("-")
        return s2 or hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]

    def _infer_title_with_scillm(context: str, timeout: float = 6.0):
        # Opt-in only to keep Stage 05 deterministic for goldens
        if os.getenv("STAGE05_LLM_INFER", "0").lower() not in {"1","true","yes","y"}:
            return None
        
        # AGENTS.md compliance: Validate SciLLM environment before making calls
        if not quick_scillm_check():
            logger.warning("SciLLM environment not configured, skipping table title inference")
            return None
            
        router = get_text_router()
        model = "chutes/text"
        prompt = (
            "You are naming a table for a technical document. Return ONLY a short title (<=10 words).\n"
            "Do not include the word 'Table' or numbering.\n\n"
            f"Context:\n{context[:1200]}\n"
        )
        try:
            import asyncio as _asyncio
            async def _call():
                resp = await router.acompletion(
                    model=model,
                    messages=[{"role":"user","content": prompt}],
                    response_format={"type":"json_object"},
                    max_tokens=64,
                    temperature=0.2,
                    timeout=timeout,
                )
                msg = getattr(resp, "choices", [{}])[0].get("message", {})
                content = msg.get("content", "").strip()
                return content.strip('"') if content else ""
            title = _asyncio.run(_call())
            return title or None
        except Exception as exc:
            log_stage_error('05_table_extractor', exc, {'context': '05'})
            raise
            logger.debug(f"Title infer via SciLLM failed: {e}")
            return None

    # --- Assign captions/titles from nearby text if missing; infer when absent ---
    for t in filtered_tables:
        page_idx = int(t.get('page_index',0))
        bbox = t.get('bbox', [0,0,0,0])
        title_src = None
        title_txt = (t.get('title') or t.get('caption') or '').strip()
        if not title_txt:
            cap = detect_table_caption(pdf_path, page_idx, bbox)
            if cap:
                title_txt = cap
                title_src = 'above'
        if not title_txt:
            # build minimal context from header row and nearby text band
            try:
                import fitz as _fitz
                with _fitz.open(str(pdf_path)) as _doc:
                    _page = _doc[page_idx]
                    r = _fitz.Rect(*bbox)
                    band = _fitz.Rect(r.x0, max(0, r.y0-120), r.x1, r.y0)
                    blks = _page.get_text('blocks', clip=band)
                    near = '\n'.join((b[4] or '').strip() for b in blks if (b[4] or '').strip())
            except Exception as exc:
                log_stage_error('05_table_extractor', exc, {'context': '05'})
                raise
                near = ''
            import pandas as _pd  # for header synthesis
            header = ''
            try:
                df = _pd.DataFrame(t.get('pandas_df') or [])
                if not df.empty:
                    # Avoid numeric column indices as titles - use meaningful content instead
                    cols = [str(c) for c in df.columns if str(c).strip()]
                    # Filter out pure numeric column names (0, 1, 2, etc.)
                    meaningful_cols = [c for c in cols if not c.isdigit()]
                    if meaningful_cols:
                        header = ' | '.join(meaningful_cols)
                    else:
                        # If all columns are numeric, use first row content instead
                        try:
                            first_row = df.iloc[0].astype(str).tolist()
                            header = ' | '.join(str(cell) for cell in first_row if str(cell).strip())[:100]
                        except Exception as exc:
                            log_stage_error('05_table_extractor', exc, {'context': '05'})
                            raise
                            header = ''
            except Exception as exc:
                log_stage_error('05_table_extractor', exc, {'context': '05'})
                raise
                pass
            ctx = f"Header: {header}\nNearby: {near}".strip()
            inferred = _infer_title_with_scillm(ctx) or (header if header else (near.split('\n',1)[0] if near else ''))
            if inferred and inferred.strip():
                title_txt = f"INFER: {inferred.strip()}"
                title_src = 'infer'
        if title_txt:
            t['title'] = title_txt
            if 'caption' not in t:
                t['caption'] = title_txt
            num, rem = _parse_table_label(title_txt)
            t['number'] = num
            base = rem.replace('(Continued)','').replace('— Continued','').strip()
            t['base_title'] = base
            t['continued'] = bool('Continued' in title_txt)
            t['title_source'] = title_src or 'detected'
            t['title_confidence'] = 0.9 if title_src in {'above','header'} else 0.6
            if num:
                t['normalized_id'] = f"table-{_slug(num)}"
            else:
                t['normalized_id'] = f"table-{_slug(base or title_txt)}"

    # --- De-duplicate header rows accidentally included in body ---
    try:
        import pandas as pd
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        pd = None  # type: ignore
    if pd is not None and TABLE_HEADER_DEDUP_ENABLED:
        for t in filtered_tables:
            try:
                df = pd.DataFrame(t.get("pandas_df") or [])
                if df.empty:
                    continue
                # Normalize headers and drop any repeated header rows found mid-body (multi-page repeats)
                cols_norm = [str(c).strip().lower() for c in df.columns]
                to_drop = []
                for idx, row in df.iterrows():
                    row_vals = [str(v).strip().lower() for v in row.tolist()]
                    pos_matches = sum(1 for a, b in zip(cols_norm, row_vals) if a == b)
                    match_ratio = pos_matches / max(1, len(cols_norm))
                    if match_ratio >= TABLE_HEADER_DUP_MIN_MATCH:
                        to_drop.append(idx)
                if to_drop:
                    df = df.drop(index=to_drop).reset_index(drop=True)
                    t["pandas_df"] = df.to_dict("records")
                    t["pandas_metrics"] = generate_pandas_metrics(df)
            except Exception as exc:
                log_stage_error('05_table_extractor', exc, {'context': '05'})
                raise
                continue

    # --- Final Payload and Output ---
    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        pass
    timings = build_stage_timings(stage_start_ts, t0)
    try:
        for _k, _v in strategy_summary.items():
            att = int(_v.get("attempts", 0) or 0)
            if att > 0:
                _v["avg_duration_ms"] = int(_v.get("total_duration_ms", 0) / att)
        timings["strategy_durations"] = strategy_summary
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        pass
    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        pass
    timings = build_stage_timings(stage_start_ts, t0)
    try:
        for _k, _v in strategy_summary.items():
            att = int(_v.get("attempts", 0) or 0)
            if att > 0:
                _v["avg_duration_ms"] = int(_v.get("total_duration_ms", 0) / att)
        timings["strategy_durations"] = strategy_summary
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        pass
    metrics_payload = {
        "quality_fallback": {
            **quality_summary,
            "retry_threshold": FRAGMENTATION_RETRY_THRESHOLD,
            "improvement_min": FRAGMENTATION_IMPROVEMENT_MIN,
        }
    }

    result = {
        "timestamp": datetime.now().isoformat(),
        "source_json": str(input_json),
        "source_pdf": str(pdf_path),
        "status": "Completed",
        "table_count": len(filtered_tables),
        "tables": filtered_tables,
        "run_id": run_id,
        "errors_count": errors_count,
        "warnings_count": warnings_count,
        "diagnostics": diagnostics,
        "timings": timings,
        "resources": resources,
        "metrics": metrics_payload,
    }
    # Optional: LLM header assist (metadata-only). Enable with TABLE_LLM_ASSIST=1.
    try:
        if os.getenv("TABLE_LLM_ASSIST", "0").lower() in ("1","true","yes","y"):
            _attach_llm_assist_headers(result, stage_output_dir)
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        diagnostics.append(
            make_event(
                "05_table_extractor",
                "warning",
                "llm_assist_failed",
                str(_assist_e),
                {},
            )
        )
    # Emit demoted text blocks so Stage 04 can merge heuristics
    if demoted_llm:
        result.setdefault("demoted_text_blocks", []).extend(demoted_llm)
    _demote_table_headers_to_text(result)
    _demote_sentence_like_single_row_tables(result)

    # Minimal schema validation
    try:
        for t in result.get("tables", []):
            assert isinstance(t.get("bbox"), (list, tuple)) and len(t.get("bbox")) == 4
            assert isinstance(t.get("page_index"), (int, float))
            # pandas_metrics optional but if present should expose shape/columns
            pm = t.get("pandas_metrics", {}) or {}
            if pm:
                _ = pm.get("shape"), pm.get("columns")
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        console.print(f"[yellow]Stage 05 schema warning: {_e}[/yellow]")

    output_path = json_output_dir / "05_tables.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    console.print(
        f"✅ Table extraction complete. Saved {len(filtered_tables)} tables to: {output_path}"
    )
    # Router lifecycle is handled by the pipeline driver via scillm.shutdown().
    return output_path


def debug_bundle(
    bundle: Path,
    output_dir: Path = Path("data/results/pipeline"),
):
    """Run Stage 05 with a consolidated bundle (sections + clean PDF)."""
    stage_output_dir = output_dir / "05_table_extractor"
    json_output_dir = stage_output_dir / "json_output"
    image_output_dir = stage_output_dir / "image_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)
    image_output_dir.mkdir(exist_ok=True)
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
                    "05_table_extractor",
                    "info",
                    "gpu_metrics_unavailable",
                    "NVML not available; GPU metrics disabled",
                    {},
                )
            )
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        pass

    data = json.loads(bundle.read_text())
    sections_obj = data.get("sections")
    clean_pdf = data.get("clean_pdf")
    if not sections_obj or not clean_pdf:
        raise ValueError("Bundle must include 'sections' and 'clean_pdf'")
    tmp_sections = stage_output_dir / "_bundle_sections.json"
    tmp_sections.write_text(json.dumps({"sections": sections_obj}))
    pdf_path = Path(clean_pdf)

    # Extract tables and associate
    all_tables, strategy_summary, quality_summary = extract_all_tables(
        pdf_path, image_output_dir, diagnostics
    )
    with open(tmp_sections, "r") as f:
        sections_data = json.load(f)
    sections = sections_data.get("sections", [])
    # associate
    for table in all_tables:
        try:
            table_bbox = fitz.Rect(table["bbox"])
            for section in sections:
                section_bbox = fitz.Rect(section["bbox"])
                if section["page_start"] <= table["page_index"] <= section[
                    "page_end"
                ] and section_bbox.intersects(table_bbox):
                    table["section_id"] = section.get("id", "unknown")
                    break
        except Exception as exc:
            log_stage_error('05_table_extractor', exc, {'context': '05'})
            raise
            continue
    # Basic filter (reuse criteria)
    filtered_tables = []
    for t in all_tables:
        metrics = t.get("pandas_metrics", {}) or {}
        shape = metrics.get("shape", [0, 0])
        rows = int(shape[0]) if isinstance(shape, (list, tuple)) and shape else 0
        density = float(metrics.get("data_density", 0.0) or 0.0)
        if (rows >= TABLE_FILTER_MIN_ROWS) or (rows >= 2 and density >= TABLE_FILTER_MIN_DENSITY):
            filtered_tables.append(t)
    if not filtered_tables and all_tables:
        # Keep all extracted tables by default (avoid data loss on multi-table pages).
        # Old behavior (collapse to a single "best" table) can be enabled via env flag.
        single = (os.getenv("STAGE05_SINGLE_PER_PAGE", "0").lower() in ("1", "true", "yes", "y"))
        if single:
            try:
                best = max(all_tables, key=lambda t: float(t.get("score", 0.0)))
                filtered_tables = [best]
            except Exception as exc:
                log_stage_error('05_table_extractor', exc, {'context': '05'})
                raise
                filtered_tables = all_tables[:1]
        else:
            filtered_tables = all_tables
            # Mark low-confidence carry-through so Stage 07 can decide merges or drops.
            for t in filtered_tables:
                t.setdefault("provenance", {})
                t["provenance"]["stage05_filter"] = "fallback_keep_all"

    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        pass
    timings = build_stage_timings(stage_start_ts, t0)
    try:
        for _k, _v in strategy_summary.items():
            att = int(_v.get("attempts", 0) or 0)
            if att > 0:
                _v["avg_duration_ms"] = int(_v.get("total_duration_ms", 0) / att)
        timings["strategy_durations"] = strategy_summary
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        pass
    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        pass
    timings = build_stage_timings(stage_start_ts, t0)
    try:
        for _k, _v in strategy_summary.items():
            att = int(_v.get("attempts", 0) or 0)
            if att > 0:
                _v["avg_duration_ms"] = int(_v.get("total_duration_ms", 0) / att)
        timings["strategy_durations"] = strategy_summary
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        pass
    metrics_payload = {
        "quality_fallback": {
            **quality_summary,
            "retry_threshold": FRAGMENTATION_RETRY_THRESHOLD,
            "improvement_min": FRAGMENTATION_IMPROVEMENT_MIN,
        }
    }

    result = {
        "timestamp": datetime.now().isoformat(),
        "source_pdf": str(pdf_path),
        "status": "Completed",
        "table_count": len(filtered_tables),
        "tables": filtered_tables,
        "run_id": run_id,
        "errors_count": errors_count,
        "warnings_count": warnings_count,
        "diagnostics": diagnostics,
        "timings": timings,
        "resources": resources,
        "metrics": metrics_payload,
    }
    # Optional: LLM assist for headers (opt-in, deterministic schema)
    try:
        if os.getenv("TABLE_LLM_ASSIST", "0").lower() in ("1", "true", "yes", "y"):
            _attach_llm_assist_headers(result, stage_output_dir)
    except Exception as exc:
        log_stage_error('05_table_extractor', exc, {'context': '05'})
        raise
        diagnostics.append(
            make_event(
                "05_table_extractor",
                "warning",
                "llm_assist_failed",
                str(_assist_e),
                {},
            )
        )

    output_path = json_output_dir / "05_tables.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    console.print(f"[green]Debug bundle: saved {len(filtered_tables)} tables to {output_path}")


## CLI removed: import and call run(...), or use a debug harness.


if __name__ == "__main__":
    import sys

    argv = sys.argv[1:]
    if argv and argv[0] == "sanity":
        sys.exit(sanity())
    print(
        "Usage: python -m extractor.pipeline.steps.05_table_extractor sanity",
        file=sys.stderr,
    )
    sys.exit(2)
