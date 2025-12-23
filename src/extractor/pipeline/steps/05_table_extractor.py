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
    try_camelot_strategy,
    extract_table_image,
    demote_table_headers_to_text as _demote_table_headers_to_text,
    demote_sentence_like_single_row_tables as _demote_sentence_like_single_row_tables,
)
from extractor.pipeline.utils.tables.runner import (
    extract_tables_from_page,
    extract_all_tables,
    run,
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
