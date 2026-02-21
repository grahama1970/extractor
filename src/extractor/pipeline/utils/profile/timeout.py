"""Pipeline timeout estimation for Stage-00 profile detection.

Provides three-tier timeout prediction:
1. learn-timeout skill (GradientBoosting, no artificial cap)
2. Legacy learned model (Ridge regression, capped)
3. Heuristic fallback (CPU-aware, formula-adjusted)

Inputs: page_count, file_size_mb, table/image/formula counts
Outputs: (timeout_seconds: int, source: str)
Failure: Falls through tiers gracefully; heuristic always succeeds
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

# Heuristic constants (seconds)
BASE_TIMEOUT_SEC = 120
SECONDS_PER_PAGE_BASE = 5
SECONDS_PER_TABLE_PAGE = 8
SECONDS_PER_TABLE_REGION = 8
SECONDS_PER_IMAGE_PAGE = 3
FORMULA_MULTIPLIER = 1.3
MAX_TIMEOUT_SEC = 7200
MIN_TIMEOUT_SEC = 120

# Memory service for dynamic learned patterns
MEMORY_SERVICE_URL = "http://127.0.0.1:8601"

_LEARNED_TIMEOUT_MODEL: Any = None
_LEARNED_MODEL_LOADED = False


def estimate_timeout(
    page_count: int,
    file_size_mb: float,
    table_pages: int = 0,
    estimated_table_count: int = 0,
    image_pages: int = 0,
    has_formulas: bool = False,
    has_requirements: bool = False,
    domain: str = "general",
    estimated_sections: int = 0,
) -> tuple[int, str]:
    """Estimate total pipeline timeout in seconds.

    Priority:
    1. learn-timeout skill (GradientBoosting, no artificial cap)
    2. Legacy learned model (Ridge regression, capped)
    3. Heuristic fallback

    Returns:
        (timeout_seconds, source) where source is
        "learn-timeout", "learned", or "heuristic"
    """
    # 1) Try learn-timeout skill first (uncapped GradientBoosting)
    lt_timeout = _predict_via_learn_timeout(
        page_count, file_size_mb, table_pages, estimated_table_count,
        image_pages, has_formulas, has_requirements, domain, estimated_sections,
    )
    if lt_timeout is not None:
        return max(lt_timeout, MIN_TIMEOUT_SEC), "learn-timeout"

    # 2) Try legacy learned model
    model = _get_learned_timeout_model()
    if model is not None:
        try:
            from extractor.pipeline.calibration.timeout_learner import (
                TimeoutFeatures,
                predict_timeout,
            )

            features = TimeoutFeatures(
                page_count=page_count,
                file_size_mb=file_size_mb,
                table_pages=table_pages,
                has_tables=table_pages > 0 or estimated_table_count > 0,
                has_figures=image_pages > 0,
                has_formulas=has_formulas,
                has_requirements=has_requirements,
                estimated_sections=estimated_sections,
                domain=domain,
            )

            timeout = predict_timeout(features, model)
            return int(min(max(timeout, MIN_TIMEOUT_SEC), MAX_TIMEOUT_SEC)), "learned"
        except Exception as e:
            logger.warning(f"Learned timeout prediction failed, using heuristic: {e}")

    # 3) Fallback to heuristic estimation
    return _estimate_timeout_heuristic(
        page_count, file_size_mb, table_pages, estimated_table_count,
        image_pages, has_formulas,
    ), "heuristic"


def _estimate_timeout_heuristic(
    page_count: int,
    file_size_mb: float,
    table_pages: int = 0,
    estimated_table_count: int = 0,
    image_pages: int = 0,
    has_formulas: bool = False,
) -> int:
    """Heuristic timeout estimation (fallback when learned model unavailable).

    Dynamically adjusts based on system resources (CPU/RAM).
    """
    system_factor = 1.0
    try:
        import multiprocessing
        cpu_count = multiprocessing.cpu_count()
        if cpu_count < 4:
            system_factor = 1.5
        elif cpu_count > 16:
            system_factor = 0.8
    except Exception:
        pass

    timeout = BASE_TIMEOUT_SEC
    size_factor = max(1.0, file_size_mb / 10)

    timeout += page_count * SECONDS_PER_PAGE_BASE * size_factor * system_factor

    if table_pages > 0:
        timeout += table_pages * SECONDS_PER_TABLE_PAGE * system_factor
    if estimated_table_count > 0:
        timeout += estimated_table_count * SECONDS_PER_TABLE_REGION * system_factor
    if image_pages > 0:
        timeout += image_pages * SECONDS_PER_IMAGE_PAGE * system_factor

    if has_formulas:
        timeout *= FORMULA_MULTIPLIER

    return int(min(max(timeout, MIN_TIMEOUT_SEC), MAX_TIMEOUT_SEC))


def _predict_via_learn_timeout(
    page_count: int,
    file_size_mb: float,
    table_pages: int = 0,
    estimated_table_count: int = 0,
    image_pages: int = 0,
    has_formulas: bool = False,
    has_requirements: bool = False,
    domain: str = "general",
    estimated_sections: int = 0,
) -> Optional[int]:
    """Try learn-timeout skill for GradientBoosting-based prediction.

    Returns recommended_timeout_seconds or None on failure.
    """
    import json as _json
    import subprocess as _sp

    skill_dir = None
    for candidate in [
        Path(__file__).resolve().parents[6] / ".pi" / "skills" / "learn-timeout",
        Path.home() / ".pi" / "skills" / "learn-timeout",
    ]:
        if (candidate / "run.sh").exists():
            skill_dir = candidate
            break

    if skill_dir is None:
        return None

    features = _json.dumps({
        "task_type": "pdf_extraction",
        "page_count": page_count,
        "file_size_mb": file_size_mb,
        "table_pages": table_pages,
        "estimated_table_count": estimated_table_count,
        "image_pages": image_pages,
        "has_tables": table_pages > 0 or estimated_table_count > 0,
        "has_figures": image_pages > 0,
        "has_formulas": has_formulas,
        "has_requirements": has_requirements,
        "estimated_sections": estimated_sections,
        "domain": domain,
    })

    try:
        result = _sp.run(
            [str(skill_dir / "run.sh"), "predict", features],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return None

        stdout = result.stdout.strip()
        json_start = stdout.find("{")
        if json_start < 0:
            return None

        data = _json.loads(stdout[json_start:])
        recommended = data.get("recommended_timeout_seconds")
        if recommended and recommended > 0:
            return int(recommended)
    except Exception:
        pass

    return None


def _get_learned_timeout_model() -> Any:
    """Load learned timeout model, trying /memory first then static file.

    Priority:
    1. Query /memory for dynamically learned coefficients
    2. Fall back to static timeout_model.json file
    3. Return None if neither available (uses heuristic fallback)
    """
    global _LEARNED_TIMEOUT_MODEL, _LEARNED_MODEL_LOADED

    if _LEARNED_MODEL_LOADED:
        return _LEARNED_TIMEOUT_MODEL

    _LEARNED_MODEL_LOADED = True

    # Try /memory first (dynamic learning)
    memory_coeffs = _query_memory_for_timeout_coeffs()
    if memory_coeffs:
        try:
            from extractor.pipeline.calibration.timeout_learner import TimeoutModel

            _LEARNED_TIMEOUT_MODEL = TimeoutModel(
                base_timeout_s=memory_coeffs.get("base", 60.0),
                sec_per_page=memory_coeffs.get("per_page", 3.0),
                sec_per_table=memory_coeffs.get("per_table", 15.0),
                sec_per_figure=memory_coeffs.get("per_figure", 5.0),
                training_r2=0.85,
                trained_on_samples=0,
            )
            logger.info("Using timeout model from /memory (dynamic)")
            return _LEARNED_TIMEOUT_MODEL
        except ImportError:
            pass

    # Fall back to static model file
    try:
        from extractor.pipeline.calibration.timeout_learner import (
            load_timeout_model,
        )

        model_path = Path(__file__).parent.parent.parent / "calibration" / "timeout_model.json"
        if model_path.exists():
            _LEARNED_TIMEOUT_MODEL = load_timeout_model(model_path)
            logger.info(
                f"Loaded learned timeout model from file "
                f"(R²={_LEARNED_TIMEOUT_MODEL.training_r2:.3f})"
            )
        else:
            logger.debug(f"No learned timeout model found at {model_path}")
    except Exception as e:
        logger.warning(f"Could not load learned timeout model: {e}")

    return _LEARNED_TIMEOUT_MODEL


def _query_memory_for_timeout_coeffs() -> Optional[Dict[str, float]]:
    """Query /memory for learned timeout coefficients.

    Searches for patterns like: "base=0.6s, per_page=1.74s, per_table=3.26s"
    stored during corpus learning.
    """
    try:
        import httpx
        import re

        response = httpx.post(
            f"{MEMORY_SERVICE_URL}/recall",
            json={
                "q": "timeout prediction model coefficients per_page per_table",
                "k": 3,
                "threshold": 0.5,
            },
            timeout=3.0,
        )

        if response.status_code != 200:
            return None

        items = response.json().get("items", [])
        if not items:
            return None

        for item in items:
            solution = item.get("solution", "")
            coeffs: Dict[str, float] = {}

            base_match = re.search(r"base[=:]\s*([\d.]+)s?", solution)
            if base_match:
                val = float(base_match.group(1))
                coeffs["base"] = val if val > 10 else val * 100

            page_match = re.search(r"per_page[=:]\s*([\d.]+)s?", solution)
            if page_match:
                coeffs["per_page"] = float(page_match.group(1))

            table_match = re.search(r"per_table[=:]\s*([\d.]+)s?", solution)
            if table_match:
                coeffs["per_table"] = float(table_match.group(1))

            figure_match = re.search(r"per_figure[=:]\s*([\d.]+)s?", solution)
            if figure_match:
                coeffs["per_figure"] = float(figure_match.group(1))

            if len(coeffs) >= 2:
                logger.info(f"Loaded timeout coefficients from /memory: {coeffs}")
                return coeffs

        return None

    except Exception as e:
        logger.debug(f"Memory query for timeout coeffs failed: {e}")
        return None
