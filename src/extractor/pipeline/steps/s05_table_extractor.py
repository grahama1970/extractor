#!/usr/bin/env python3
"""
Pipeline Stage 5: Table Extraction using Camelot (Refactored)
=============================================================

This stage extracts tables from PDFs using Camelot's lattice detection.

Refactored to be self-contained (merged from utils/tables/runner.py).
Helpers split into:
  - extractor.pipeline.utils.tables.ml_prediction
  - extractor.pipeline.utils.tables.memory_params
  - extractor.pipeline.utils.tables.llm_assist
"""

import os
import sys
import json
import math
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Third-party
try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF (fitz) not installed. Stage 05 requires it.", file=sys.stderr)
    raise

try:
    import camelot  # noqa: F401
except ImportError:
    print("Camelot is required for Stage 05 (table extraction).", file=sys.stderr)
    raise

try:
    import pandas as pd
except ImportError:
    pd = None

from dotenv import load_dotenv, find_dotenv
from loguru import logger
from rich.console import Console

# Pipeline Utilities
from extractor.pipeline.utils.diagnostics import (
    get_run_id,
)
from extractor.pipeline.utils.step_sanity import run_step_sanity

# Table Utils (keep these external as they are granular helpers)
from extractor.pipeline.utils.tables import (
    CAMELOT_STRATEGIES,
    generate_pandas_metrics as _generate_pandas_metrics,
    score_table as _score_table,
    iou,
    try_camelot_strategy,
    extract_table_image,
    demote_single_column_tables as _demote_single_column_tables,
    demote_sentence_like_single_row_tables as _demote_sentence_like_single_row_tables,
    demote_text_heavy_lattice_tables,
    bbox_tuple_for,
    fragmentation_score,
    fragmentation_score_with_domain,
    should_retry_fragmentation,
    has_fragmentation_improvement,
    should_replace_table,
    sanitize_cell,
    coalesce_repeated_header_rows,
    predict_strategy,
    log_disagreement,
    should_skip_sweep,
    STRATEGY_SELECTOR_MODE,
    pre_rasterize_page,
    cleanup_raster_cache,
)

# ML Prediction helpers (Shadow S00, strategy predictor)
from extractor.pipeline.utils.tables.ml_prediction import (
    SHADOW_S00_ENABLED,
    _get_shadow_s00_prediction,
    USE_STRATEGY_PREDICTOR,
    _get_strategy_predictor,
    _predict_strategy_for_table,
)

# Memory / agent-tuned parameter helpers
from extractor.pipeline.utils.tables.memory_params import (
    _query_memory_for_params,
    _get_preset_table_config,
    _pdf_doc_prefix,
    _load_table_hint,
    _should_store_params,
    _store_successful_params_to_memory,
)

# LLM assist header detection
from extractor.pipeline.utils.tables.llm_assist import (
    _stable_table_hash,
    _headers_from_table,
    _should_assist,
    _attach_llm_assist_headers,
)


# --- Initialization ---
load_dotenv(find_dotenv())
console = Console()
STEP_NAME = "05_table_extractor"

# Constants
VERTICAL_PADDING_RATIO = float(os.getenv("TABLE_VERTICAL_PADDING_RATIO", 0.30))
HORIZONTAL_PADDING_RATIO = float(os.getenv("TABLE_HORIZONTAL_PADDING_RATIO", 0.07))
PYMUPDF_DPI = int(os.getenv("TABLE_EXTRACTION_DPI", 200))
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
TABLE_MULTI_PAGE_MERGE_ENABLED = os.getenv("TABLE_MULTI_PAGE_MERGE_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
    "y",
)
TABLE_MULTI_PAGE_MERGE_MIN_IOU = float(os.getenv("TABLE_MULTI_PAGE_MERGE_MIN_IOU", 0.3))
TABLE_SELECT_ONE_PER_PAGE = os.getenv("TABLE_SELECT_ONE_PER_PAGE", "false").lower() in (
    "1",
    "true",
    "yes",
    "y",
)
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
FRAGMENTATION_RETRY_THRESHOLD = int(os.getenv("TABLE_FRAGMENTATION_RETRY_THRESHOLD", 0))
FRAGMENTATION_IMPROVEMENT_MIN = int(os.getenv("TABLE_FRAGMENTATION_MIN_IMPROVEMENT", 1))

# Parallel page extraction: number of worker processes
# Default: cpu_count//4 capped at 12 (each worker uses ~55MB for fitz+Camelot+OpenCV)
S05_WORKERS = int(os.getenv("S05_WORKERS", str(min((os.cpu_count() or 4) // 4, 12))))


# ------------------------------------------------------------------
# EXTRACTION LOGIC
# ------------------------------------------------------------------


def extract_tables_from_page(
    pdf_path: Path,
    page_num: int,
    pdf_doc: Any,
    output_dir: Path,
    last_good_strategy: Optional[str] = None,
    diagnostics: Optional[list] = None,
    category: Optional[str] = None,
    s00_expected_tables: int = 0,
    s00_table_style: Optional[str] = None,
    s00_domain: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str], Dict[str, Any], Dict[str, Any]]:

    page_tables = {}
    best_strategy = None
    page_metrics = {"retry_candidates": 0, "fallback_tables": 0, "fallback_applied": False}
    strategy_durations = {}

    # Strategy Selector: get prediction before sweep
    strategy_prediction = predict_strategy(
        table_style=s00_table_style,
        domain=s00_domain,
        category=category,
    )

    # Strategy Selection
    baseline_name = "lattice_default"
    if last_good_strategy in CAMELOT_STRATEGIES:
        baseline_name = last_good_strategy

    strategies_to_try = [{"name": baseline_name, **CAMELOT_STRATEGIES[baseline_name]}]
    fallback_strategies = []

    # ML-based strategy prediction (if enabled)
    # Skip predictor when S00 found zero table evidence -- saves ~2s/page
    predictor_suggestion = None
    if USE_STRATEGY_PREDICTOR and s00_expected_tables > 0:
        # Get a sample region from the page center (common table location)
        try:
            page = pdf_doc[page_num]
            pw, ph = page.rect.width, page.rect.height
            # Sample center 60% of page (typical table area)
            sample_bbox = (pw * 0.2, ph * 0.2, pw * 0.8, ph * 0.8)
            predictor_suggestion = _predict_strategy_for_table(
                pdf_doc, page_num, sample_bbox, category
            )
            if predictor_suggestion and predictor_suggestion.get("confidence", 0) >= 0.80:
                # Use predicted strategy as baseline
                pred_name = predictor_suggestion["name"]
                if pred_name in CAMELOT_STRATEGIES:
                    baseline_name = pred_name
                    strategies_to_try = [{"name": baseline_name, **CAMELOT_STRATEGIES[baseline_name]}]
                    page_metrics["ml_predicted"] = True
                    page_metrics["ml_confidence"] = predictor_suggestion["confidence"]
        except Exception as e:
            logger.debug(f"Strategy prediction failed for page {page_num}: {e}")

    others = sorted(
        [k for k in CAMELOT_STRATEGIES.keys() if k != baseline_name],
        key=lambda x: 0 if "lattice" in CAMELOT_STRATEGIES[x]["flavor"] else 1,
    )
    for nm in others:
        fallback_strategies.append({"name": nm, **CAMELOT_STRATEGIES[nm]})

    def _quantize_bbox(bt):
        return tuple(round(float(x), 2) for x in bt)

    def _register(st_name, tbl, bbox_k, scr):
        nonlocal best_strategy
        # Use domain-aware fragmentation scoring for scientific papers
        domain = "scientific" if category and category.lower() == "scientific" else "general"
        new_frag = fragmentation_score_with_domain(tbl.df, domain)
        existing = page_tables.get(bbox_k)

        if existing:
            ex_frag = int(existing.get("fragmentation", 0))
            ex_score = float(existing.get("score", 0))
            if "lattice" in existing.get("strategy", "") and "stream" in st_name:
                if ex_score > 10 and ex_frag < 100:
                    return "skipped", bool(existing.get("quality_fallback"))

            if not should_replace_table(ex_frag, new_frag, ex_score, scr):
                return "skipped", bool(existing.get("quality_fallback"))

            existing["history"].append(
                {"strategy": st_name, "fragmentation": new_frag, "score": scr}
            )
            fallback = existing.get("quality_fallback")
            if st_name != existing.get("strategy") and (
                has_fragmentation_improvement(ex_frag, new_frag)
                or should_retry_fragmentation(ex_frag)
            ):
                fallback = True

            page_tables[bbox_k].update(
                {
                    "table": tbl,
                    "score": scr,
                    "strategy": st_name,
                    "fragmentation": new_frag,
                    "quality_fallback": fallback,
                }
            )
            if fallback:
                page_metrics["fallback_applied"] = True
            best_strategy = st_name
            return "replaced", fallback

        fallback = st_name != baseline_name
        page_tables[bbox_k] = {
            "table": tbl,
            "score": scr,
            "strategy": st_name,
            "fragmentation": new_frag,
            "history": [{"strategy": st_name, "fragmentation": new_frag, "score": scr}],
            "quality_fallback": fallback,
        }
        if fallback:
            page_metrics["fallback_applied"] = True
        best_strategy = st_name
        return "added", fallback

    # Pre-rasterize page once for lattice strategy reuse.
    _has_multiple_lattice = sum(
        1 for s in strategies_to_try + fallback_strategies if s.get("flavor") == "lattice"
    ) > 1
    _raster_cached = False
    if _has_multiple_lattice:
        try:
            pre_rasterize_page(pdf_path, page_num, output_dir)
            _raster_cached = True
        except Exception as exc:
            logger.debug(f"Raster pre-cache failed for page {page_num}: {exc}")

    # Execute Strategies
    _tried_stream = False

    for strat in strategies_to_try + fallback_strategies:
        is_stream = strat.get("flavor") == "stream"

        # Check if we can stop (only loop fallbacks if needed)
        has_fragmentation = any(
            should_retry_fragmentation(int(p["fragmentation"] or 0)) for p in page_tables.values()
        ) if page_tables else False
        needs_more = not page_tables or has_fragmentation

        # Always try at least one stream strategy
        should_try_stream = is_stream and not _tried_stream

        if strat in fallback_strategies and not needs_more and not should_try_stream:
            break

        # Track after break check so stream strategies are always executed
        if is_stream:
            _tried_stream = True
            logger.info(
                f"S05 trying stream: page={page_num+1} "
                f"lattice_found={len(page_tables)} "
                f"strategy={strat.get('name')}"
            )

        t0 = time.monotonic()
        tables = try_camelot_strategy(pdf_path, page_num, strat, diagnostics)
        dt = int((time.monotonic() - t0) * 1000)

        sn = strat["name"]
        strategy_durations.setdefault(sn, {"count": 0, "total_ms": 0, "found": {}})
        strategy_durations[sn]["count"] += 1
        strategy_durations[sn]["total_ms"] += dt

        found = 0
        for t in tables:
            bbox = bbox_tuple_for(t)
            score = _score_table(t.df)
            if score == 0 or not bbox:
                continue

            bq = _quantize_bbox(bbox)
            replaced = False
            for k in list(page_tables.keys()):
                if iou(bq, k) >= 0.70:
                    _register(sn, t, k, score)
                    replaced = True
                    break
            if not replaced:
                action, _ = _register(sn, t, bq, score)
                if action in ("added", "replaced"):
                    found += 1

        strategy_durations[sn]["found"][page_num] = found

        # Early exit after baseline only if no fragmentation AND we've tried stream.
        if (
            strat["name"] == baseline_name
            and found > 0
            and all(p.get("fragmentation", 0) == 0 for p in page_tables.values())
            and _tried_stream
        ):
            break

    # Log strategy outcome for Shadow-LEGO training
    if STRATEGY_SELECTOR_MODE != "off":
        tried_names = list(strategy_durations.keys())
        frag_scores = {}
        for sn, sd in strategy_durations.items():
            for pt_info in page_tables.values():
                for h in pt_info.get("history", []):
                    if h.get("strategy") == sn:
                        frag_scores[sn] = int(h.get("fragmentation", 0))

        all_frags = list(frag_scores.values())
        lattice_found = 0
        stream_found = 0
        for sn, sd in strategy_durations.items():
            count = sd["found"].get(page_num, 0)
            if count == 0:
                continue
            if sn in ("agent_tuned", "memory_learned"):
                actual_flavor = CAMELOT_STRATEGIES.get(sn, {}).get("flavor", "")
            else:
                actual_flavor = CAMELOT_STRATEGIES.get(sn, {}).get("flavor", sn)
            if "lattice" in actual_flavor:
                lattice_found += count
            else:
                stream_found += count
        page_stats = {
            "num_tables": len(page_tables),
            "num_strategies_tried": len(tried_names),
            "max_fragmentation": max(all_frags) if all_frags else 0,
            "has_fragmentation": int(any(f > 0 for f in all_frags)),
            "lattice_found": lattice_found,
            "stream_found": stream_found,
        }

        _actual_flavor = None
        if best_strategy:
            _bs_info = CAMELOT_STRATEGIES.get(best_strategy, {})
            _actual_flavor = _bs_info.get("flavor", best_strategy)

        log_disagreement(
            page_num=page_num,
            predicted=strategy_prediction,
            actual_best=best_strategy,
            strategies_tried=tried_names,
            frag_scores=frag_scores,
            output_dir=output_dir,
            s00_table_style=s00_table_style,
            s00_domain=s00_domain,
            category=category,
            page_stats=page_stats,
            actual_flavor=_actual_flavor,
        )

    # Clean up raster cache for this page
    if _raster_cached:
        cleanup_raster_cache(output_dir, page_num)

    # Build Result
    extracted = []
    idx = 0
    for bbox_k, info in page_tables.items():
        tbl = info["table"]
        bbox = list(bbox_k)
        # Normalize Coords Top-Left
        try:
            pg = pdf_doc[page_num]
            H = pg.rect.height
            bbox = [bbox[0], H - bbox[3], bbox[2], H - bbox[1]]  # y0=H-y1, y1=H-y0
        except Exception as e:
            logger.debug(f"Failed to normalize bbox coordinates for page {page_num}: {e}")

        img_path = extract_table_image(
            pdf_doc, page_num, getattr(tbl, "_bbox", None), output_dir, idx, diagnostics
        )
        if not img_path:
            try:
                rect = fitz.Rect(bbox)
                if rect.is_empty or rect.width <= 0 or rect.height <= 0:
                    rect = fitz.Rect(pg.rect)
                rect = rect & pg.rect
                pix = pg.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect)
                fallback_path = output_dir / f"page_{page_num+1}_table_{idx+1}_fallback.png"
                pix.save(str(fallback_path))
                img_path = str(fallback_path)
            except Exception:
                img_path = None

        df = tbl.df
        if TABLE_HEADER_COALESCE_ENABLED:
            try:
                df = coalesce_repeated_header_rows(df, TABLE_HEADER_REPEAT_MIN_MATCH)
            except Exception as e:
                logger.debug(f"Header row coalescing failed: {e}")

        df_clean = df.map(sanitize_cell)

        extracted.append(
            {
                "page_number": page_num + 1,
                "page_index": page_num,
                "table_index": idx + 1,
                "bbox": bbox,
                "extraction_method": "camelot",
                "strategy": info["strategy"],
                "fragmentation_score": info["fragmentation"],
                "pandas_df": df_clean.to_dict("records"),
                "pandas_metrics": _generate_pandas_metrics(df_clean),
                "camelot_metrics": {
                    "accuracy": getattr(tbl, "accuracy", None),
                    "whitespace": getattr(tbl, "whitespace", None),
                },
                "score": info["score"],
                "quality_fallback": info["quality_fallback"],
                "strategy_history": info["history"],
                "table_image_path": (
                    str(Path(img_path).resolve().relative_to(output_dir.parent.parent.resolve()))
                    if img_path
                    else None
                ),
            }
        )
        idx += 1

    # Populate fallback metrics from extracted results
    page_metrics["fallback_tables"] = sum(1 for t in extracted if t.get("quality_fallback"))

    return extracted, best_strategy, strategy_durations, page_metrics


def _page_worker(
    pdf_path_str: str,
    page_num: int,
    output_dir_str: str,
    initial_strategy: Optional[str],
    strategies_dict: Dict[str, Dict],
    category: Optional[str],
    s00_per_page: int,
    s00_table_style: Optional[str],
    s00_domain: Optional[str],
) -> Dict[str, Any]:
    """Process one page in a subprocess. All args/returns are picklable.

    Re-opens the PDF per worker since fitz.Document is not picklable.
    """
    pdf_path = Path(pdf_path_str)
    output_dir = Path(output_dir_str)

    import fitz as _fitz

    doc = _fitz.open(str(pdf_path))
    local_diagnostics: List[Dict[str, Any]] = []

    # Inject strategies snapshot into module-level dict
    CAMELOT_STRATEGIES.update(strategies_dict)

    try:
        tabs, best, sdurs, mets = extract_tables_from_page(
            pdf_path, page_num, doc, output_dir,
            last_good_strategy=initial_strategy,
            diagnostics=local_diagnostics,
            category=category,
            s00_expected_tables=s00_per_page,
            s00_table_style=s00_table_style,
            s00_domain=s00_domain,
        )
    finally:
        doc.close()

    return {
        "page_num": page_num,
        "tables": tabs,
        "best_strategy": best,
        "strategy_durations": sdurs,
        "page_metrics": mets,
        "diagnostics": local_diagnostics,
    }


def _empty_page_result(page_num: int) -> Dict[str, Any]:
    """Fallback result for a failed page worker."""
    return {
        "page_num": page_num,
        "tables": [],
        "best_strategy": None,
        "strategy_durations": {},
        "page_metrics": {"retry_candidates": 0, "fallback_tables": 0, "fallback_applied": False},
        "diagnostics": [],
    }


def extract_all_tables(
    pdf_path: Path,
    output_dir: Path,
    diagnostics: list = None,
    preset: Optional[str] = None,
    category: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    s00_table_pages: int = 0,
    s00_estimated_table_count: int = 0,
):
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        raise RuntimeError(f"Open PDF failed: {exc}")

    all_tables = []
    strategy_summary = {}
    quality_summary = {
        "pages_processed": 0,
        "pages_with_tables": 0,
        "pages_with_fallback": 0,
        "tables_with_fallback": 0,
        "param_source": None,
        "params_used": {},
    }
    last_good = None
    params_used = {}

    # Priority order for table extraction parameters:
    # 1. Agent-tuned hint (from table-lab skill) - most specific
    # 2. Memory service (learned patterns from corpus)
    # 3. Preset config (from twin_config.yml features)
    # 4. Default strategies

    param_source = None

    # 1. Check for agent-tuned hint (from table-lab skill)
    hint = _load_table_hint(preset, category, pdf_path=pdf_path)
    if hint:
        # S00 safety check: don't force lattice on borderless tables.
        # Agent hints from table-lab may be stale or domain-generic.
        _hint_flavor = hint["flavor"]
        _s00_style = (context or {}).get("table_style", "none")
        if _hint_flavor == "lattice" and _s00_style == "borderless":
            logger.warning(
                f"Agent hint forces lattice but S00 says borderless — "
                f"overriding to stream_default for {pdf_path}"
            )
            _hint_flavor = "stream"
            hint = {**hint, "flavor": "stream"}
            # Clear lattice-specific params, use stream defaults
            hint.pop("line_scale", None)
            hint.pop("process_background", None)
            if not hint.get("edge_tol"):
                hint["edge_tol"] = 50

        custom = {"flavor": _hint_flavor, "params": {}}
        if hint.get("line_scale"):
            custom["params"]["line_scale"] = hint["line_scale"]
            custom["params"]["process_background"] = hint.get("process_background", False)
        if hint.get("edge_tol"):
            custom["params"]["edge_tol"] = hint["edge_tol"]
        CAMELOT_STRATEGIES["agent_tuned"] = custom
        last_good = "agent_tuned"
        param_source = "agent_hint"
        params_used = {"flavor": _hint_flavor, **custom["params"]}

    # 2. Try memory service for learned parameters (if no agent hint)
    if not last_good and preset:
        domain = (context or {}).get("domain", "general") if context else "general"
        memory_params = _query_memory_for_params(preset, domain)
        if memory_params:
            custom = {"flavor": memory_params.get("flavor", "lattice"), "params": {}}
            if memory_params.get("line_scale"):
                custom["params"]["line_scale"] = memory_params["line_scale"]
            if memory_params.get("edge_tol"):
                custom["params"]["edge_tol"] = memory_params["edge_tol"]
            CAMELOT_STRATEGIES["memory_learned"] = custom
            last_good = "memory_learned"
            param_source = "memory"
            params_used = {"flavor": memory_params.get("flavor", "lattice"), **custom["params"]}

    # 3. Try preset config (from twin_config.yml features)
    if not last_good and context:
        preset_params = _get_preset_table_config(context)
        if preset_params:
            custom = {"flavor": preset_params.get("flavor", "lattice"), "params": {}}
            if preset_params.get("line_scale"):
                custom["params"]["line_scale"] = preset_params["line_scale"]
            if preset_params.get("edge_tol"):
                custom["params"]["edge_tol"] = preset_params["edge_tol"]
            CAMELOT_STRATEGIES["preset_config"] = custom
            last_good = "preset_config"
            param_source = "preset"
            params_used = {"flavor": preset_params.get("flavor", "lattice"), **custom["params"]}

    quality_summary["param_source"] = param_source
    quality_summary["params_used"] = params_used

    # ---------------------------------------------------------------
    # S00 Profile-Driven Strategy Routing (TASK-003)
    # ---------------------------------------------------------------
    s00_table_style = (context or {}).get("table_style", "none")
    s00_domain = (context or {}).get("domain", "general")
    s00_multi_col = (context or {}).get("has_multi_column", False)

    if not last_good:
        if s00_table_style == "borderless":
            last_good = "stream_default"
            param_source = param_source or "s00_routing"
            quality_summary["s00_routed_strategy"] = "stream_default"
            logger.info(f"S00 routing: table_style=borderless -> stream_default first")
        elif s00_table_style == "bordered":
            if s00_domain == "defense":
                last_good = "lattice_strong"
                quality_summary["s00_routed_strategy"] = "lattice_strong"
                logger.info(f"S00 routing: table_style=bordered, domain=defense -> lattice_strong")
        elif s00_table_style == "mixed":
            quality_summary["s00_routed_strategy"] = "mixed_sweep"
            logger.info(f"S00 routing: table_style=mixed -> full strategy sweep")

    # Multi-column layout: increase horizontal padding for better capture
    if s00_multi_col:
        os.environ.setdefault("TABLE_HORIZONTAL_PADDING_RATIO", "0.15")

    quality_summary["s00_table_style"] = s00_table_style
    quality_summary["s00_domain"] = s00_domain

    # Shadow S00 prediction (Shadow-LEGO seed producer)
    shadow_prediction = {}
    if SHADOW_S00_ENABLED and context:
        profile_path = output_dir.parent / "00_profile_detector" / "profile.json"
        s00_profile = {}
        if profile_path.exists():
            try:
                s00_profile = json.loads(profile_path.read_text())
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to read S00 profile from {profile_path}: {e}")
        if s00_profile:
            shadow_prediction = _get_shadow_s00_prediction(s00_profile)
            if shadow_prediction:
                quality_summary["shadow_s00"] = shadow_prediction
                if shadow_prediction.get("needs_stream") and shadow_prediction.get("stream_confidence", 0) >= 0.6:
                    if "stream_default" in CAMELOT_STRATEGIES and not last_good:
                        last_good = "stream_default"
                        quality_summary["shadow_s00_applied"] = True
                        logger.info(
                            f"Shadow S00: needs_stream predicted (conf={shadow_prediction['stream_confidence']:.2f}), "
                            f"prioritizing stream_default strategy"
                        )

    # Compute per-page expected table count from S00 estimates.
    s00_per_page = 0
    if s00_table_pages > 0:
        if s00_estimated_table_count > 0:
            s00_per_page = math.ceil(s00_estimated_table_count / s00_table_pages)
            s00_per_page = min(s00_per_page, 10)
        else:
            s00_per_page = 1
            logger.info(
                f"S00 table_pages={s00_table_pages} but estimated_table_count=0; "
                f"defaulting s00_per_page=1 to enable stream fallback"
            )

    total_pages = len(doc)

    def _merge_page_result(r: Dict[str, Any]) -> None:
        """Merge a single page result into aggregate structures."""
        pn = r["page_num"]
        tabs = r["tables"]
        best = r["best_strategy"]
        sdurs = r["strategy_durations"]
        mets = r["page_metrics"]

        if tabs:
            all_tables.extend(tabs)

        quality_summary["pages_processed"] += 1
        if tabs:
            quality_summary["pages_with_tables"] += 1
        if mets["fallback_applied"]:
            quality_summary["pages_with_fallback"] += 1
        quality_summary["tables_with_fallback"] += mets["fallback_tables"]

        for k, v in sdurs.items():
            entry = strategy_summary.setdefault(
                k, {"attempts": 0, "successes": 0, "failures": 0, "total_duration_ms": 0}
            )
            entry["attempts"] += v["count"]
            entry["total_duration_ms"] += v["total_ms"]
            if v["found"].get(pn, 0) > 0:
                entry["successes"] += 1
            else:
                entry["failures"] += 1

    use_parallel = S05_WORKERS > 1 and total_pages > 4

    if not use_parallel:
        # Sequential mode -- existing behavior with last_good propagation
        try:
            for page_num in range(total_pages):
                logger.info(f"Processing page {page_num + 1}/{total_pages}")
                tabs, best, sdurs, mets = extract_tables_from_page(
                    pdf_path, page_num, doc, output_dir, last_good, diagnostics, category,
                    s00_expected_tables=s00_per_page,
                    s00_table_style=s00_table_style,
                    s00_domain=s00_domain,
                )
                if best:
                    last_good = best
                _merge_page_result({
                    "page_num": page_num,
                    "tables": tabs,
                    "best_strategy": best,
                    "strategy_durations": sdurs,
                    "page_metrics": mets,
                    "diagnostics": [],
                })
                if diagnostics is not None and mets:
                    pass  # diagnostics already appended in-process
        finally:
            doc.close()
    else:
        # Parallel mode -- workers re-open PDF independently
        doc.close()
        strategies_snapshot = dict(CAMELOT_STRATEGIES)
        initial_strategy = last_good  # Pre-computed from S00 profile

        logger.info(
            f"S05 parallel mode: {S05_WORKERS} workers for {total_pages} pages"
        )

        page_results: Dict[int, Dict[str, Any]] = {}
        with ProcessPoolExecutor(max_workers=S05_WORKERS) as pool:
            futures = {
                pool.submit(
                    _page_worker,
                    str(pdf_path),
                    pn,
                    str(output_dir),
                    initial_strategy,
                    strategies_snapshot,
                    category,
                    s00_per_page,
                    s00_table_style,
                    s00_domain,
                ): pn
                for pn in range(total_pages)
            }
            for future in as_completed(futures):
                pn = futures[future]
                try:
                    page_results[pn] = future.result()
                except Exception as exc:
                    logger.error(f"Page {pn + 1} worker failed: {exc}")
                    page_results[pn] = _empty_page_result(pn)

        # Merge results in page order (preserves table ordering)
        for pn in sorted(page_results):
            r = page_results[pn]
            _merge_page_result(r)
            if diagnostics is not None:
                diagnostics.extend(r.get("diagnostics", []))

    # Filter out single-column false positives (lists, code blocks, etc)
    filtered_tables = []
    for t in all_tables:
        pm = (t.get("pandas_metrics") or {}).get("shape") or []
        cols = int(pm[1]) if len(pm) > 1 and str(pm[1]).isdigit() else 2
        if cols >= 2:
            filtered_tables.append(t)
        else:
            logger.debug(f"Filtered single-column table on page {t.get('page_number')}")

    return filtered_tables, strategy_summary, quality_summary


# ------------------------------------------------------------------
# RUNNER ENTRY POINT
# ------------------------------------------------------------------


def run(
    input_json: Path,
    pdf_dir: Path = Path("data/results/pipeline/01_annotation_processor"),
    output_dir: Path = Path("data/results/pipeline"),
):
    console.print(f"[green]Extracting tables based on sections in: {input_json.name}[/green]")
    stage_output_dir = output_dir / "05_table_extractor"
    json_output_dir = stage_output_dir / "json_output"
    image_output_dir = stage_output_dir / "visual_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)
    image_output_dir.mkdir(exist_ok=True)

    logger.add(stage_output_dir / "stage_05.log", level="INFO")

    if not input_json.exists():
        raise FileNotFoundError("Input JSON missing")
    sections_data = json.load(open(input_json))

    # Robust PDF Selection
    pdf_path = None

    # 1. Try explicit 'clean_pdf' key
    clean_key = sections_data.get("clean_pdf")
    if clean_key and Path(clean_key).exists():
        pdf_path = Path(clean_key)

    # 2. Try deriving from 'source_pdf' key
    if not pdf_path:
        src_key = sections_data.get("source_pdf")
        if src_key:
            stem = Path(src_key).stem
            candidate = pdf_dir / f"{stem}_clean.pdf"
            if candidate.exists():
                pdf_path = candidate

    # 3. Fallback (Dangerous but legacy support)
    if not pdf_path:
        try:
            pdf_path = next(pdf_dir.glob("*_clean.pdf"))
        except StopIteration:
            raise FileNotFoundError(f"No *_clean.pdf found in {pdf_dir}")

    # Load preset from pipeline_context.json for hint lookup and preset config
    preset_name = None
    preset_category = None
    pipeline_ctx = None
    context_file = output_dir / "pipeline_context.json"
    if context_file.exists():
        try:
            pipeline_ctx = json.loads(context_file.read_text())
            preset_name = pipeline_ctx.get("preset_name")
            preset_category = (pipeline_ctx.get("config") or {}).get("category")
        except (json.JSONDecodeError, OSError) as e:
            logger.debug(f"Failed to read pipeline context for preset info: {e}")

    t0 = time.monotonic()

    # Pass S00 table estimates so S05 tries stream on pages where lattice misses borderless tables
    _s00_table_pages = (pipeline_ctx or {}).get("table_pages", 0)
    _s00_est_tables = (pipeline_ctx or {}).get("estimated_table_count", 0)
    if _s00_table_pages == 0 and _s00_est_tables > 0:
        _s00_table_pages = (pipeline_ctx or {}).get("table_pages_drawing", 0) or 1

    all_tables, st_sum, q_sum = extract_all_tables(
        pdf_path, image_output_dir, [],
        preset=preset_name, category=preset_category, context=pipeline_ctx,
        s00_table_pages=_s00_table_pages,
        s00_estimated_table_count=_s00_est_tables,
    )

    # Filter Section Headers from tables
    sections = sections_data.get("sections", [])
    sec_titles = {s.get("title", "").strip().lower() for s in sections if s.get("title")}

    filtered = []
    for t in all_tables:
        # If single column and matches a section title -> drop
        pm = t.get("pandas_metrics", {})
        shape = pm.get("shape", [0, 0])
        if int(shape[1] or 0) == 1:
            txt = (
                " ".join(
                    [
                        str(v)
                        for r in t.get("pandas_df", [])
                        for v in (r.values() if isinstance(r, dict) else r)
                    ]
                )
                .strip()
                .lower()
            )
            if any(st in txt for st in sec_titles if len(st) > 5):
                continue
        filtered.append(t)

    # Section Association
    for t in filtered:
        t_box = fitz.Rect(t["bbox"])
        for s in sections:
            if s["page_start"] <= t["page_index"] <= s["page_end"] and fitz.Rect(
                s["bbox"]
            ).intersects(t_box):
                t["section_id"] = s.get("id")
                break

    # Generate Output
    res = {
        "timestamp": datetime.now().isoformat(),
        "source_pdf": str(pdf_path),
        "status": "Completed",
        "table_count": len(filtered),
        "tables": filtered,
        "run_id": get_run_id(),
        "metrics": {"quality": q_sum, "strategies": st_sum},
        "timings": {"duration": int((time.monotonic() - t0) * 1000)},
        "quality_summary": q_sum,
    }

    # Add quality warnings to output
    quality_warnings = []
    for t in filtered:
        hdrs = _headers_from_table(t)
        if hdrs and all(str(h).isdigit() for h in hdrs):
            quality_warnings.append(f"Table {t.get('table_index')}: generic integer headers")
    res["quality_warnings"] = quality_warnings

    # Enable LLM assist by default in accurate mode
    llm_assist_default = "0"
    if os.getenv("PIPELINE_MODE") == "accurate" or os.getenv("USE_LLM") == "1":
        llm_assist_default = "1"

    if os.getenv("TABLE_LLM_ASSIST", llm_assist_default).lower() in ("1", "true", "yes", "y"):
        try:
            _attach_llm_assist_headers(res, stage_output_dir)
        except Exception as e:
            logger.warning(f"Failed to attach LLM assist headers: {e}")

    _demote_single_column_tables(res)
    _demote_sentence_like_single_row_tables(res)
    demote_text_heavy_lattice_tables(res)

    out_path = json_output_dir / "05_tables.json"
    out_path.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    console.print(f"Saved {len(filtered)} tables to {out_path}")

    # Continuous Learning: Store successful params to /memory
    s00_estimate = (pipeline_ctx or {}).get("estimated_table_count", 0)
    if _should_store_params(q_sum, filtered, s00_estimate):
        domain = (pipeline_ctx or {}).get("config", {}).get("category", "general")
        if isinstance(domain, str):
            domain = domain.lower()
        _store_successful_params_to_memory(
            pdf_name=pdf_path.name,
            preset=preset_name or "unknown",
            domain=domain or "general",
            strategy_summary=st_sum,
            quality_summary=q_sum,
            table_count=len(filtered),
        )

    return out_path


def sanity() -> int:
    return run_step_sanity(STEP_NAME)


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Stage 05: Table Extractor")
    parser.add_argument(
        "--pipeline-dir", type=Path, required=True, help="Path to pipeline results root"
    )
    args = parser.parse_args()

    pipeline_dir = args.pipeline_dir

    try:
        logger.info("Running Stage 05...")
        s1_dir = pipeline_dir / "01_annotation_processor"

        s4_json = pipeline_dir / "04_section_builder/json_output/04_sections.json"
        if not s4_json.exists():
            logger.error("Missing S04 output (sections)")
            sys.exit(1)

        run(input_json=s4_json, pdf_dir=s1_dir, output_dir=pipeline_dir)

    except Exception as e:
        logger.error(f"Execution failed: {e}")
        sys.exit(1)
