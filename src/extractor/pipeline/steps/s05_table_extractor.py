#!/usr/bin/env python3
"""
Pipeline Stage 5: Table Extraction using Camelot (Refactored)
=============================================================

This stage extracts tables from PDFs using Camelot's lattice detection.

Refactored to be self-contained (merged from utils/tables/runner.py).
"""

import os
import sys
import json
import asyncio
import time
import hashlib
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
# Shadow S00 classifier (Shadow-LEGO seed producer)
SHADOW_S00_ENABLED = os.environ.get("SHADOW_S00", "false").lower() == "true"
_shadow_s00_predictor = None

def _get_shadow_s00_prediction(profile: dict) -> dict:
    """Get Shadow S00 prediction. Returns empty dict on any failure.

    This is a SEED PRODUCER — informs strategy ordering, never gates.
    """
    global _shadow_s00_predictor
    if not SHADOW_S00_ENABLED:
        return {}
    try:
        if _shadow_s00_predictor is None:
            # Import from sibling pi-mono repo. Use env var or path discovery.
            scripts_dir = os.environ.get("SHADOW_S00_SCRIPTS_DIR", "")
            if not scripts_dir:
                # Auto-discover from extractor repo → pi-mono sibling
                extractor_root = Path(__file__).resolve().parents[5]
                scripts_dir = str(extractor_root.parent / "pi-mono" / ".pi" / "skills" / "create-table-classifier" / "scripts")
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)
            from shadow_s00_inference import ShadowS00Predictor
            _shadow_s00_predictor = ShadowS00Predictor()
        pred = _shadow_s00_predictor.predict(profile)
        return {
            "predicted_class": pred.predicted_class,
            "needs_stream": pred.needs_stream,
            "stream_confidence": pred.stream_confidence,
            "class_probabilities": pred.class_probabilities,
        }
    except Exception as e:
        logger.debug(f"Shadow S00 prediction failed (non-blocking): {e}")
        return {}

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
)


def _stable_table_hash(t: Dict[str, Any]) -> str:
    # Hash based on content to be stable across runs
    df_recs = t.get("pandas_df", [])
    s = json.dumps(df_recs, sort_keys=True)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _headers_from_table(t: Dict[str, Any]) -> List[str]:
    # Try to get headers from pandas metric or infer row 0
    # simplified for this context
    df_recs = t.get("pandas_df", [])
    if not df_recs:
        return []
    return list(df_recs[0].keys())


def _should_assist(t: Dict[str, Any]) -> bool:
    # Assist if simple headers like 0, 1, 2 or empty strings
    hdrs = _headers_from_table(t)
    if not hdrs:
        return False
    # Check for integer-like headers (Pandas defaults)
    if all(str(h).isdigit() for h in hdrs):
        return True
    # Check for empty headers
    if any(not str(h).strip() for h in hdrs):
        return True
    return False


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

# Strategy Predictor (ML-based strategy selection)
USE_STRATEGY_PREDICTOR = os.getenv("USE_STRATEGY_PREDICTOR", "false").lower() in (
    "1",
    "true",
    "yes",
    "y",
)
STRATEGY_PREDICTOR_CONFIDENCE_THRESHOLD = float(
    os.getenv("STRATEGY_PREDICTOR_CONFIDENCE_THRESHOLD", 0.75)
)
STRATEGY_PREDICTOR_MODEL_PATH = os.getenv(
    "STRATEGY_PREDICTOR_MODEL_PATH",
    "/home/graham/workspace/experiments/pi-mono/.pi/skills/create-table-classifier/models/table-classifier-ensemble-final",
)

# Global predictor instance (lazy loaded)
_strategy_predictor = None


def _get_strategy_predictor():
    """Lazy load the strategy predictor."""
    global _strategy_predictor
    if _strategy_predictor is not None:
        return _strategy_predictor

    if not USE_STRATEGY_PREDICTOR:
        return None

    try:
        model_path = Path(STRATEGY_PREDICTOR_MODEL_PATH)
        if not model_path.exists():
            logger.warning(f"Strategy predictor model not found at {model_path}")
            return None

        # Import from the skill
        sys.path.insert(0, str(model_path.parent.parent / "scripts"))
        from inference import TableStrategyPredictor

        _strategy_predictor = TableStrategyPredictor(model_path)
        logger.info(f"Loaded strategy predictor from {model_path}")
        return _strategy_predictor

    except Exception as e:
        logger.warning(f"Failed to load strategy predictor: {e}")
        return None


def _predict_strategy_for_table(
    pdf_doc: Any,
    page_num: int,
    bbox: Tuple[float, float, float, float],
    preset: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Use ML predictor to suggest optimal strategy for a table region.

    Args:
        pdf_doc: PyMuPDF document
        page_num: Page number (0-indexed)
        bbox: Table bounding box (x0, y0, x1, y1)
        preset: Optional preset hint

    Returns:
        Dict with strategy name, params, confidence or None
    """
    predictor = _get_strategy_predictor()
    if predictor is None:
        return None

    try:
        from PIL import Image
        import io

        # Extract table region image
        page = pdf_doc[page_num]
        clip = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
        mat = fitz.Matrix(2, 2)  # 2x zoom for better quality
        pix = page.get_pixmap(matrix=mat, clip=clip)
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data)).convert("RGB")

        # Get prediction
        pred = predictor.predict(img, preset=preset)

        if pred.confidence < STRATEGY_PREDICTOR_CONFIDENCE_THRESHOLD:
            logger.debug(
                f"Predictor confidence {pred.confidence:.2f} below threshold, skipping"
            )
            return None

        # Map to CAMELOT_STRATEGIES name
        strategy_name = pred.strategy
        if strategy_name == "lattice_sensitive":
            strategy_name = "lattice_sensitive"
        elif strategy_name == "stream":
            strategy_name = "stream_default"
        else:
            strategy_name = "lattice_default"

        logger.info(
            f"Predictor suggests {strategy_name} (conf={pred.confidence:.2f}, "
            f"line_scale={pred.line_scale}, edge_tol={pred.edge_tol})"
        )

        return {
            "name": strategy_name,
            "flavor": pred.flavor,
            "line_scale": pred.line_scale,
            "edge_tol": pred.edge_tol,
            "confidence": pred.confidence,
            "predicted": True,
        }

    except Exception as e:
        logger.debug(f"Strategy prediction failed: {e}")
        return None


# Memory service URL for learned parameters
MEMORY_SERVICE_URL = os.getenv("MEMORY_SERVICE_URL", "http://127.0.0.1:8601")


def _query_memory_for_params(preset: str, domain: str = "general") -> Optional[Dict[str, Any]]:
    """Query /memory for learned extraction parameters.

    Searches for patterns learned during corpus processing that match
    the current preset/domain. Returns optimal Camelot parameters if found.

    Args:
        preset: The detected preset name (e.g., "arxiv", "requirements_spec")
        domain: The document domain (e.g., "scientific", "engineering")

    Returns:
        Dict with learned parameters (line_scale, edge_tol, flavor) or None
    """
    try:
        import httpx

        query = f"table extraction {preset} {domain} optimal parameters line_scale"

        response = httpx.post(
            f"{MEMORY_SERVICE_URL}/recall",
            json={"q": query, "k": 5, "threshold": 0.5},
            timeout=5.0,
        )

        if response.status_code != 200:
            return None

        items = response.json().get("items", [])
        if not items:
            return None

        # Parse parameters from top match
        for item in items:
            solution = item.get("solution", "")

            # Look for parameter patterns in the solution text
            params = {}

            # Extract line_scale — matches both plain (line_scale=40)
            # and JSON key formats ("best_line_scale": 40) from table-lab
            import re
            ls_match = re.search(r"(?:best_)?line_scale[\"'\s]*[=:]\s*(\d+)", solution)
            if ls_match:
                params["line_scale"] = int(ls_match.group(1))

            # Extract edge_tol — same dual-format matching
            et_match = re.search(r"(?:best_)?edge_tol[\"'\s]*[=:]\s*(\d+)", solution)
            if et_match:
                params["edge_tol"] = int(et_match.group(1))

            # Extract flavor — match both plain text mentions and JSON
            # key format ("best_flavor": "stream") from table-lab --json
            flavor_match = re.search(r'(?:best_)?flavor["\'\s]*[=:]\s*["\']?(\w+)', solution)
            if flavor_match:
                fl = flavor_match.group(1).lower()
                if "stream" in fl:
                    params["flavor"] = "stream"
                else:
                    params["flavor"] = "lattice"
            elif "lattice_sensitive" in solution:
                params["flavor"] = "lattice"
            elif "stream" in solution:
                params["flavor"] = "stream"
            elif "lattice" in solution:
                params["flavor"] = "lattice"

            if params:
                logger.info(f"Loaded learned params from /memory: {params}")
                return params

        return None

    except Exception as e:
        logger.debug(f"Memory query failed (non-critical): {e}")
        return None


def _get_preset_table_config(context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract table extraction configuration from preset features.

    The preset may specify table_strategy, line_scale, edge_tol in its
    features section (from twin_config.yml).

    Args:
        context: Pipeline context containing preset_match info

    Returns:
        Dict with table extraction params or None
    """
    try:
        features = context.get("config", {}).get("features", {})
        if not features:
            return None

        params = {}

        if features.get("table_strategy"):
            strategy = features["table_strategy"]
            if "sensitive" in strategy:
                params["flavor"] = "lattice"
                params["line_scale"] = features.get("line_scale", 12)
            elif "stream" in strategy:
                params["flavor"] = "stream"
            else:
                params["flavor"] = "lattice"

        if features.get("line_scale"):
            params["line_scale"] = features["line_scale"]

        if features.get("edge_tol"):
            params["edge_tol"] = features["edge_tol"]

        if params:
            logger.info(f"Using preset table config: {params}")
            return params

        return None

    except Exception as e:
        logger.debug(f"Failed to extract preset table config: {e}")
        return None


# ------------------------------------------------------------------
# LLM ASSIST HELPERS
# ------------------------------------------------------------------


def _attach_llm_assist_headers(result: Dict[str, Any], stage_dir: Path) -> None:
    logger.info("Starting TABLE_LLM_ASSIST check...")
    sidecar = stage_dir / "05_tables_llm_assist.json"
    side_data = json.loads(sidecar.read_text()) if sidecar.exists() else {}

    model = (
        os.getenv("TABLE_LLM_ASSIST_MODEL")
        or os.getenv("CHUTES_TEXT_MODEL")
        or "deepseek-ai/DeepSeek-V3"
    ).strip()
    if not model:
        return

    tables = result.get("tables") or []
    # Headers are stored in pandas_metrics.columns, not in a top-level 'headers' field
    candidates = [t for t in tables if any(str(h).isdigit() for h in t.get("pandas_metrics", {}).get("columns", []))]

    if not candidates:
        logger.info(f"TABLE_LLM_ASSIST: No generic headers found in {len(tables)} tables.")
        return

    logger.info(
        f"TABLE_LLM_ASSIST: Found {len(candidates)} tables with generic headers. Proceeding."
    )
    requests = []
    table_map = {}

    tokens_used = 0
    tokens_budget = int(os.getenv("STAGE05_TOKENS_BUDGET", "120000"))
    budget_enforce = os.getenv("STAGE05_BUDGET_ENFORCE", "true").lower() in (
        "1",
        "true",
        "yes",
        "y",
    )

    system_prompt = (
        "You are a strict normalizer for table column headers.\n"
        "Rules: Do not invent, add, or reorder columns.\n"
        'Return JSON: {"headers": [..]} with the same length as input.\n'
    )

    for idx, t in enumerate(tables):
        if budget_enforce and tokens_used >= tokens_budget:
            logger.warning("TABLE_LLM_ASSIST: Tokens budget exceeded")
            continue

        if not _should_assist(t):
            logger.debug(
                f"TABLE_LLM_ASSIST: Skipping Table {t.get('table_index')} - does not satisfy assist criteria"
            )
            continue

        headers_in = _headers_from_table(t)
        if not headers_in:
            logger.warning(
                f"TABLE_LLM_ASSIST: Table {t.get('table_index')} has no headers to assist"
            )
            continue

        table_hash = _stable_table_hash(t)
        cache_key = f"assist:{table_hash}:{model}"
        cached = side_data.get(cache_key)

        if (
            cached
            and isinstance(cached.get("headers"), list)
            and len(cached["headers"]) == len(headers_in)
        ):
            logger.info(f"TABLE_LLM_ASSIST: Using cached headers for Table {t.get('table_index')}")
            t["llm_assist"] = {"model": model, "patch": cached}
            t["header_inferred"] = [sanitize_cell(h) for h in cached["headers"]]
            continue

        logger.info(
            f"TABLE_LLM_ASSIST: Queuing assist request for Table {t.get('table_index')} using model {model}"
        )
        user_content = json.dumps({"headers_input": headers_in}, ensure_ascii=False)
        requests.append(
            {
                "model": model,  # Use the model variable
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0,
                "index": idx,
                "metadata": {"headers_in": headers_in, "table_hash": table_hash},
            }
        )
        table_map[idx] = t

    if not requests:
        return

    from scillm.batch import parallel_acompletions_iter

    async def process_batch():
        nonlocal tokens_used
        api_base = os.getenv("SCILLM_API_BASE", "https://llm.chutes.ai/v1")
        api_key = os.getenv("CHUTES_API_KEY")

        async for r in parallel_acompletions_iter(
            requests,
            api_base=api_base,
            api_key=api_key,
            custom_llm_provider="openai_like",
            concurrency=5,
            timeout=20,
            wall_time_s=120,
            tenacious=True,
            response_format={"type": "json_object"},
        ):
            idx = r.get("index")
            t = table_map.get(idx)
            if not t:
                continue

            if not r["ok"]:
                continue
            tokens_used += r.get("usage", {}).get("total_tokens") or 0

            try:
                data = r.get("parsed") or r.get("content") or {}
                if isinstance(data, str) and data:
                    import json_repair

                    data = json_repair.loads(data)

                new_headers = data.get("headers")
                if isinstance(new_headers, list) and len(new_headers) == len(
                    t.get("header_inferred", []) or requests[idx]["metadata"]["headers_in"]
                ):
                    new_headers = [" ".join(str(h).split()) for h in new_headers]
                    t["llm_assist"] = {"model": model, "patch": {"headers": new_headers}}
                    t["header_inferred"] = [sanitize_cell(h) for h in new_headers]
                    side_data[f"assist:{requests[idx]['metadata']['table_hash']}:{model}"] = {
                        "headers": new_headers
                    }
            except Exception:
                pass

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(process_batch())
    finally:
        loop.close()

    try:
        sidecar.write_text(json.dumps(side_data, ensure_ascii=False, indent=2))
    except Exception:
        pass


# ------------------------------------------------------------------
# AGENT-TUNED HINT LOADING (table-lab skill integration)
# ------------------------------------------------------------------

_TABLE_HINTS_FILENAME = "table_hints.json"


_TABLE_HINTS_FALLBACK_PATH = Path("/mnt/storage12tb/extractor_corpus/metadata") / _TABLE_HINTS_FILENAME


def _pdf_doc_prefix(name: str) -> str:
    """Extract document identifier prefix for family matching.

    Iteratively strips corpus suffixes (_clean, _HEXHASH, _changeN, _RevN,
    _NoticeN, vN) until stable, leaving just the document identifier.

    Examples:
        "MIL-STD-882E_change1.pdf"          -> "MIL-STD-882E"
        "MIL-STD-882E_990b0e_clean.pdf"     -> "MIL-STD-882E"
        "NIST.SP.800-53B_8a9dae_clean.pdf"  -> "NIST.SP.800-53B"
        "ECSS-E-ST-10-03C_Rev1.pdf"         -> "ECSS-E-ST-10-03C"
        "MIL-HDBK-217F_Notice2_clean.pdf"   -> "MIL-HDBK-217F"
        "2412.08819v1_abc123_clean.pdf"      -> "2412.08819"
    """
    import re
    stem = Path(name).stem
    # Iteratively strip known suffixes until stable
    suffix_re = re.compile(
        r'(_clean|_change\d*|_[Nn]otice\d*|_[Rr]ev\d*|_[0-9a-f]{6,8}|_[0-9a-f]{4,5})$'
    )
    prev = None
    while stem != prev:
        prev = stem
        stem = suffix_re.sub('', stem)
    # Strip trailing version: v1, v2 etc
    stem = re.sub(r'v\d+$', '', stem)
    stem = stem.rstrip('_')
    return stem


def _load_table_hint(
    preset: Optional[str] = None,
    category: Optional[str] = None,
    hints_file: Optional[Path] = None,
    pdf_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Load agent-tuned Camelot strategy hint for a preset:category pair.

    Reads from CORPUS_ROOT/metadata/table_hints.json (written by table-lab skill).
    Tries multiple key formats to handle vocabulary mismatch between
    table-lab hint keys and S00 preset/category names.

    As a last resort, matches by source_pdf document family — if the current
    PDF shares a document identifier prefix with a hint's source_pdf, that
    hint is used. This bridges the total vocabulary gap between table-lab
    keys (e.g. "mil_std:standards") and S00 presets (e.g. "requirements_spec").

    Returns hint dict or None if no hint found.
    """
    if hints_file is None:
        corpus_root = os.environ.get("CORPUS_ROOT", "")
        if corpus_root:
            hints_file = Path(corpus_root) / "metadata" / _TABLE_HINTS_FILENAME
        elif _TABLE_HINTS_FALLBACK_PATH.exists():
            hints_file = _TABLE_HINTS_FALLBACK_PATH
        else:
            return None

    if not hints_file.exists():
        return None

    try:
        data = json.loads(hints_file.read_text())
        hints = data.get("hints", {})
        if not hints:
            return None

        # Strategy 1: Key-based matching (requires preset)
        if preset:
            candidates = [
                f"{preset}:{category or ''}",           # exact: "requirements_spec:Engineering"
                f"{preset}:{(category or '').lower()}",  # lowered category
                f"{preset}:",                            # preset-only
                preset,                                  # bare preset
            ]
            for key in candidates:
                hint = hints.get(key)
                if hint:
                    logger.info(f"Loaded agent-tuned hint (key={key}): {hint.get('flavor')} "
                                f"(ls={hint.get('line_scale')}, et={hint.get('edge_tol')})")
                    return hint

            # Prefix scan on hint keys
            preset_lower = preset.lower()
            for hint_key, hint_val in hints.items():
                if hint_key.lower().startswith(preset_lower + ":") or hint_key.lower() == preset_lower:
                    logger.info(f"Loaded agent-tuned hint (fuzzy key={hint_key} for preset={preset}): "
                                f"{hint_val.get('flavor')} (ls={hint_val.get('line_scale')}, "
                                f"et={hint_val.get('edge_tol')})")
                    return hint_val

        # Strategy 2: source_pdf family matching (bridges total vocabulary gap)
        if pdf_path:
            current_prefix = _pdf_doc_prefix(pdf_path.name)
            if current_prefix and len(current_prefix) >= 4:
                for hint_key, hint_val in hints.items():
                    source_pdf = hint_val.get("source_pdf", "")
                    if not source_pdf:
                        continue
                    hint_prefix = _pdf_doc_prefix(source_pdf)
                    if hint_prefix and current_prefix == hint_prefix:
                        logger.info(
                            f"Loaded agent-tuned hint (source_pdf family match: "
                            f"{pdf_path.name} ~ {source_pdf}, key={hint_key}): "
                            f"{hint_val.get('flavor')} (ls={hint_val.get('line_scale')}, "
                            f"et={hint_val.get('edge_tol')})")
                        return hint_val

        return None
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"Failed to load table hints: {exc}")
        return None


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
) -> Tuple[List[Dict[str, Any]], Optional[str], Dict[str, Any], Dict[str, Any]]:

    page_tables = {}
    best_strategy = None
    page_metrics = {"retry_candidates": 0, "fallback_tables": 0, "fallback_applied": False}
    strategy_durations = {}

    # Strategy Selection
    baseline_name = "lattice_default"
    if (
        last_good_strategy in CAMELOT_STRATEGIES
        and "lattice" in CAMELOT_STRATEGIES[last_good_strategy]["flavor"]
    ):
        baseline_name = last_good_strategy

    strategies_to_try = [{"name": baseline_name, **CAMELOT_STRATEGIES[baseline_name]}]
    fallback_strategies = []

    # ML-based strategy prediction (if enabled)
    # Skip predictor when S00 found zero table evidence — saves ~2s/page
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

    # Execute Strategies
    # Always try stream as a fallback after lattice — borderless tables are invisible
    # to lattice mode. S00's table estimates are approximate (PyMuPDF heuristics) and
    # unreliable as a gatekeeper, so we always try stream rather than gating on S00.
    _tried_stream = False

    for strat in strategies_to_try + fallback_strategies:
        is_stream = strat.get("flavor") == "stream"

        # Check if we can stop (only loop fallbacks if needed)
        has_fragmentation = any(
            should_retry_fragmentation(int(p["fragmentation"] or 0)) for p in page_tables.values()
        ) if page_tables else False
        needs_more = not page_tables or has_fragmentation

        # Always try at least one stream strategy — borderless tables are common
        # in datasheets, defense specs, and engineering docs. Don't gate on S00.
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
        # Always try stream before stopping — borderless tables need it.
        if (
            strat["name"] == baseline_name
            and found > 0
            and all(p.get("fragmentation", 0) == 0 for p in page_tables.values())
            and _tried_stream
        ):
            break

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
        except Exception:
            pass

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
            except Exception:
                pass

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
        "param_source": None,  # Track where params came from
        "params_used": {},  # Actual params used (for /memory storage)
    }
    last_good = None
    params_used = {}  # Track actual params for storage in /memory

    # Priority order for table extraction parameters:
    # 1. Agent-tuned hint (from table-lab skill) - most specific
    # 2. Memory service (learned patterns from corpus)
    # 3. Preset config (from twin_config.yml features)
    # 4. Default strategies

    param_source = None

    # 1. Check for agent-tuned hint (from table-lab skill)
    hint = _load_table_hint(preset, category, pdf_path=pdf_path)
    if hint:
        custom = {"flavor": hint["flavor"], "params": {}}
        if hint.get("line_scale"):
            custom["params"]["line_scale"] = hint["line_scale"]
            custom["params"]["process_background"] = hint.get("process_background", False)
        if hint.get("edge_tol"):
            custom["params"]["edge_tol"] = hint["edge_tol"]
        CAMELOT_STRATEGIES["agent_tuned"] = custom
        last_good = "agent_tuned"
        param_source = "agent_hint"
        params_used = {"flavor": hint["flavor"], **custom["params"]}

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

    # Shadow S00 prediction (Shadow-LEGO seed producer)
    # If the classifier predicts this PDF needs stream mode, reorder strategies
    # to try stream FIRST instead of last. This is a seed, not a gate.
    shadow_prediction = {}
    if SHADOW_S00_ENABLED and context:
        # Load S00 profile from pipeline context or disk
        profile_path = output_dir.parent / "00_profile_detector" / "profile.json"
        s00_profile = {}
        if profile_path.exists():
            try:
                s00_profile = json.loads(profile_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        if s00_profile:
            shadow_prediction = _get_shadow_s00_prediction(s00_profile)
            if shadow_prediction:
                quality_summary["shadow_s00"] = shadow_prediction
                if shadow_prediction.get("needs_stream") and shadow_prediction.get("stream_confidence", 0) >= 0.6:
                    # Reorder: put stream_default BEFORE lattice strategies
                    # This dramatically speeds up extraction for borderless-table PDFs
                    if "stream_default" in CAMELOT_STRATEGIES and not last_good:
                        last_good = "stream_default"
                        quality_summary["shadow_s00_applied"] = True
                        logger.info(
                            f"Shadow S00: needs_stream predicted (conf={shadow_prediction['stream_confidence']:.2f}), "
                            f"prioritizing stream_default strategy"
                        )

    # Compute per-page expected table count from S00 estimates.
    # If S00 says 20 tables across 5 table_pages, expect ~4 per page on average.
    # Use ceil to be aggressive — better to try stream than miss borderless tables.
    #
    # IMPORTANT: S00 often has table_pages > 0 (page-level visual evidence of tables)
    # but estimated_table_count == 0 (text-based estimator couldn't count them).
    # In that case, assume at least 1 table per flagged page so stream gets tried.
    import math
    s00_per_page = 0
    if s00_table_pages > 0:
        if s00_estimated_table_count > 0:
            s00_per_page = math.ceil(s00_estimated_table_count / s00_table_pages)
            # Cap at reasonable max to avoid pathological S00 overestimates
            s00_per_page = min(s00_per_page, 10)
        else:
            # table_pages > 0 but estimated_table_count == 0:
            # S00 found page-level table evidence but couldn't estimate count.
            # Default to 1 expected table per page — enough to trigger stream fallback.
            s00_per_page = 1
            logger.info(
                f"S00 table_pages={s00_table_pages} but estimated_table_count=0; "
                f"defaulting s00_per_page=1 to enable stream fallback"
            )

    try:
        for page_num in range(len(doc)):
            logger.info(f"Processing page {page_num + 1}/{len(doc)}")
            tabs, best, sdurs, mets = extract_tables_from_page(
                pdf_path, page_num, doc, output_dir, last_good, diagnostics, category,
                s00_expected_tables=s00_per_page,
            )

            if tabs:
                all_tables.extend(tabs)
            if best:
                last_good = best

            quality_summary["pages_processed"] += 1
            if tabs:
                quality_summary["pages_with_tables"] += 1
            if mets["fallback_applied"]:
                quality_summary["pages_with_fallback"] += 1
            quality_summary["tables_with_fallback"] += mets["fallback_tables"]

            # Aggregate timings
            for k, v in sdurs.items():
                entry = strategy_summary.setdefault(
                    k, {"attempts": 0, "successes": 0, "failures": 0, "total_duration_ms": 0}
                )
                entry["attempts"] += v["count"]
                entry["total_duration_ms"] += v["total_ms"]
                if v["found"].get(page_num, 0) > 0:
                    entry["successes"] += 1
                else:
                    entry["failures"] += 1

    finally:
        doc.close()

    # De-dupe overlap across pages regression check (rare but safe)
    # (Leaving out heavy dedup logic for brevity, reliance on per-page bbox logic mostly sufficient)

    # Filter out single-column false positives (lists, code blocks, etc)
    # This runs early so downstream stages don't process junk
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
# CONTINUOUS LEARNING: STORE SUCCESSFUL PARAMS TO /MEMORY
# ------------------------------------------------------------------

MEMORY_BASE_URL = os.getenv("MEMORY_BASE_URL", "http://127.0.0.1:8601")


def _should_store_params(quality_summary: Dict, tables: List, s00_estimate: int = 0) -> bool:
    """Check if extraction quality is good enough to store params.

    Only stores if:
    1. No fallback strategies needed (tables_with_fallback == 0)
    2. At least 1 table was extracted
    3. S00 estimate is within 3x of actual (if available)

    Returns:
        True if params should be stored to /memory.
    """
    if not tables:
        return False

    # No fallback strategies used
    if quality_summary.get("tables_with_fallback", 0) > 0:
        logger.debug("Skipping memory storage: fallback strategies were used")
        return False

    # Check S00 vs actual ratio if estimate provided
    if s00_estimate > 0:
        actual = len(tables)
        ratio = actual / s00_estimate
        if ratio < 0.3 or ratio > 3.0:
            logger.debug(f"Skipping memory storage: S00/S05 ratio {ratio:.2f} out of range")
            return False

    return True


def _store_successful_params_to_memory(
    pdf_name: str,
    preset: str,
    domain: str,
    strategy_summary: Dict[str, Any],
    quality_summary: Dict[str, Any],
    table_count: int,
) -> bool:
    """Store successful extraction parameters to /memory for future recall.

    Args:
        pdf_name: Name of the processed PDF.
        preset: Preset that was used (e.g., "arxiv_scientific").
        domain: Document domain (e.g., "scientific", "engineering").
        strategy_summary: Summary of strategies attempted and success rates.
        quality_summary: Quality metrics from extraction.
        table_count: Number of tables extracted.

    Returns:
        True if successfully stored, False otherwise.
    """
    try:
        import httpx
    except ImportError:
        logger.debug("httpx not available for /memory storage")
        return False

    # Find the best-performing strategy
    best_strategy = None
    best_success_rate = 0.0
    for name, stats in strategy_summary.items():
        attempts = stats.get("attempts", 0)
        successes = stats.get("successes", 0)
        if attempts > 0:
            rate = successes / attempts
            if rate > best_success_rate:
                best_success_rate = rate
                best_strategy = name

    if not best_strategy:
        return False

    # Construct lesson
    lesson = {
        "problem": f"Table extraction for {preset or 'unknown'} {domain} documents",
        "solution": f"Best strategy: {best_strategy} ({best_success_rate*100:.0f}% success rate)",
        "context": f"Tested on {pdf_name}, extracted {table_count} tables with 0 fallbacks",
        "tags": ["s05", "camelot", preset or "unknown", domain, best_strategy],
    }

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(f"{MEMORY_BASE_URL}/add", json=lesson)
            if resp.status_code == 200:
                logger.info(f"Stored successful S05 params to /memory: {best_strategy} for {preset}")
                return True
            else:
                logger.debug(f"Failed to store to /memory: {resp.status_code}")
                return False
    except httpx.ConnectError:
        logger.debug("/memory service not available, skipping param storage")
        return False
    except Exception as e:
        logger.debug(f"Failed to store params to /memory: {e}")
        return False


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
        except (json.JSONDecodeError, OSError):
            pass

    t0 = time.monotonic()

    # Pass S00 table estimates so S05 tries stream on pages where lattice misses borderless tables
    _s00_table_pages = (pipeline_ctx or {}).get("table_pages", 0)
    _s00_est_tables = (pipeline_ctx or {}).get("estimated_table_count", 0)
    # S00 sometimes has table_pages=0 but detected tables via drawing objects or keywords.
    # Fall back to table_pages_drawing so stream still gets tried for borderless tables.
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
            if any(st in txt for st in sec_titles if len(st) > 5):  # simple substring check
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
        "quality_summary": q_sum,  # Top-level for easier /memory storage
    }

    # Add quality warnings to output
    quality_warnings = []
    for t in filtered:
        hdrs = _headers_from_table(t)
        if hdrs and all(str(h).isdigit() for h in hdrs):
            quality_warnings.append(f"Table {t.get('table_index')}: generic integer headers")
    res["quality_warnings"] = quality_warnings

    # Enable LLM assist by default in accurate mode (detected via env var or explicit flag)
    # We check TABLE_LLM_ASSIST environment first, then fallback to "1" if accurate mode is likely
    llm_assist_default = "0"
    if os.getenv("PIPELINE_MODE") == "accurate" or os.getenv("USE_LLM") == "1":
        llm_assist_default = "1"

    if os.getenv("TABLE_LLM_ASSIST", llm_assist_default).lower() in ("1", "true", "yes", "y"):

        try:
            _attach_llm_assist_headers(res, stage_output_dir)
        except Exception:
            pass

    # _demote_table_headers_to_text(res)  # DISABLED: Causing "Junk" output (0,1,2 headers)
    _demote_single_column_tables(res)  # Filter single-column false positives (lists, code blocks, etc)
    _demote_sentence_like_single_row_tables(res)
    demote_text_heavy_lattice_tables(res)

    out_path = json_output_dir / "05_tables.json"
    out_path.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    console.print(f"✅ Saved {len(filtered)} tables to {out_path}")

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
