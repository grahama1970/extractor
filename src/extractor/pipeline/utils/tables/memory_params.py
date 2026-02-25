"""Memory/agent parameter storage for Stage 05.

Contains:
- Memory service query for learned extraction parameters
- Preset table config extraction
- Agent-tuned hint loading (table-lab skill integration)
- Continuous learning: storing successful params to /memory
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


# ------------------------------------------------------------------
# MEMORY SERVICE QUERY
# ------------------------------------------------------------------

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

            # Extract line_scale -- matches both plain (line_scale=40)
            # and JSON key formats ("best_line_scale": 40) from table-lab
            ls_match = re.search(r"(?:best_)?line_scale[\"'\s]*[=:]\s*(\d+)", solution)
            if ls_match:
                params["line_scale"] = int(ls_match.group(1))

            # Extract edge_tol -- same dual-format matching
            et_match = re.search(r"(?:best_)?edge_tol[\"'\s]*[=:]\s*(\d+)", solution)
            if et_match:
                params["edge_tol"] = int(et_match.group(1))

            # Extract flavor -- match both plain text mentions and JSON
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


# ------------------------------------------------------------------
# PRESET TABLE CONFIG
# ------------------------------------------------------------------


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
# AGENT-TUNED HINT LOADING (table-lab skill integration)
# ------------------------------------------------------------------

_TABLE_HINTS_FILENAME = "table_hints.json"

_CORPUS_ROOT = Path(os.getenv("CORPUS_ROOT", "/mnt/storage12tb/extractor_corpus"))
_TABLE_HINTS_FALLBACK_PATH = _CORPUS_ROOT / "metadata" / _TABLE_HINTS_FILENAME


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

    As a last resort, matches by source_pdf document family -- if the current
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
    except Exception as e:
        if "ConnectError" in type(e).__name__:
            logger.debug("/memory service not available, skipping param storage")
        else:
            logger.debug(f"Failed to store params to /memory: {e}")
        return False
