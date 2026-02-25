#!/usr/bin/env python3
"""Strategy Selector for S05 Table Extraction.

3-tier cascade predicting the optimal Camelot strategy per page:

| Tier | Method                              | Availability    |
|------|-------------------------------------|-----------------|
| 0    | S00 profile heuristic               | Always          |
| 0.5  | Tabular classifier on outcomes      | After training  |
| 2    | scillm VLM with page image          | When reachable  |

Shadow-LEGO pattern: predict + brute-force + log disagreements.
learn-datalake daemon harvests 05_strategy_outcomes.jsonl files
to train the Tier 0.5 classifier via /classifier-lab.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

STRATEGY_SELECTOR_MODE = os.getenv("STRATEGY_SELECTOR_MODE", "shadow")
# "shadow" = predict + brute-force, log disagreements (default)
# "active" = use prediction, skip sweep if confident
# "off"    = brute-force only (current behavior)

_ACTIVE_CONFIDENCE_THRESHOLD = float(
    os.getenv("STRATEGY_SELECTOR_CONFIDENCE", "0.85")
)

# /assistant skill path for cascade classify
_ASSISTANT_RUN = Path.home() / ".pi/skills/assistant/run.sh"

# Tier 0.5 classifier path (populated by /classifier-lab or learn-datalake)
_CLASSIFIER_MODEL_PATH = os.getenv(
    "STRATEGY_CLASSIFIER_MODEL",
    "models/table-strategy-classifier/model.joblib",
)
_LABEL_ENCODER_PATH = os.getenv(
    "STRATEGY_LABEL_ENCODER",
    "models/table-strategy-classifier/label_encoder.joblib",
)
_classifier = None  # lazy-loaded
_label_encoder = None  # lazy-loaded
_feature_order = None  # lazy-loaded from metrics.json

# 21-feature schema matching train_strategy.py
_FEATURE_COLS = [
    "table_style_borderless", "table_style_bordered", "table_style_mixed",
    "domain_scientific", "domain_defense", "domain_engineering",
    "num_tables", "num_strategies_tried", "max_fragmentation",
    "has_fragmentation", "lattice_found", "stream_found",
    "frag_lattice_default", "frag_lattice_strong",
    "frag_stream_default", "frag_stream_tight", "frag_stream_wide",
    "frag_stream_columns", "frag_agent_tuned", "frag_memory_learned",
]
_KNOWN_CATEGORIES = [
    "unknown", "scientific", "defense", "financial", "medical", "legal", "general",
]
_CAT_ENCODER = {cat: i for i, cat in enumerate(_KNOWN_CATEGORIES)}


@dataclass
class StrategyPrediction:
    """Result of the strategy selector cascade."""

    strategy_name: str  # e.g. "lattice_default", "stream_default"
    confidence: float
    tier: str  # "heuristic", "classifier", "vlm"
    features: Dict[str, Any] = field(default_factory=dict)


def _tier0_heuristic(
    table_style: Optional[str],
    domain: Optional[str],
    has_borders: Optional[bool],
) -> StrategyPrediction:
    """Tier 0: Rule-based prediction from S00 profile fields."""
    # Borderless / no borders detected
    if table_style == "borderless" or has_borders is False:
        return StrategyPrediction(
            strategy_name="stream_default",
            confidence=0.70,
            tier="heuristic",
            features={"rule": "borderless"},
        )

    # Bordered + defense domain → heavier line detection
    if table_style == "bordered" and domain == "defense":
        return StrategyPrediction(
            strategy_name="lattice_strong",
            confidence=0.80,
            tier="heuristic",
            features={"rule": "bordered_defense"},
        )

    # Bordered (any other domain)
    if table_style == "bordered":
        return StrategyPrediction(
            strategy_name="lattice_default",
            confidence=0.75,
            tier="heuristic",
            features={"rule": "bordered"},
        )

    # Mixed / unknown → low confidence lattice default
    return StrategyPrediction(
        strategy_name="lattice_default",
        confidence=0.50,
        tier="heuristic",
        features={"rule": "mixed_or_unknown"},
    )


def _tier05_assistant(
    table_style: Optional[str],
    domain: Optional[str],
    has_borders: Optional[bool],
    category: Optional[str],
) -> Optional[StrategyPrediction]:
    """Try /assistant classify for the full cascade (heuristic → classifier → GPT).

    Returns None if /assistant unavailable or classification fails.
    """
    if not _ASSISTANT_RUN.exists():
        return None

    features_payload = json.dumps({
        "table_style": table_style or "unknown",
        "domain": domain or "unknown",
        "has_borders": int(bool(has_borders)),
        "category": category or "unknown",
    })

    try:
        result = subprocess.run(
            [
                str(_ASSISTANT_RUN), "classify",
                "--task", "table-strategy-selector",
                "--text", features_payload,
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return StrategyPrediction(
                strategy_name=data["prediction"],
                confidence=float(data.get("confidence", 0.0)),
                tier="classifier",
                features={"source": "assistant"},
            )
    except Exception:
        pass
    return None


def _build_feature_vector(
    table_style: Optional[str] = None,
    domain: Optional[str] = None,
    category: Optional[str] = None,
    num_tables: int = 0,
    num_strategies_tried: int = 0,
    max_fragmentation: int = 0,
    has_fragmentation: int = 0,
    lattice_found: int = 0,
    stream_found: int = 0,
    frag_scores: Optional[Dict[str, int]] = None,
) -> list:
    """Build 21-feature vector for the strategy classifier.

    Returns a list ordered by _feature_order (from metrics.json) if available,
    otherwise falls back to _FEATURE_COLS + category order.

    Pre-sweep calls leave post-sweep features at defaults (0 or -1).
    Post-sweep calls (confirm_strategy) populate all features.
    """
    ts = table_style or "unknown"
    dom = domain or "unknown"
    fs = frag_scores or {}

    feature_dict: Dict[str, float] = {
        # table_style one-hot (3)
        "table_style_borderless": float(int(ts == "borderless")),
        "table_style_bordered": float(int(ts == "bordered")),
        "table_style_mixed": float(int(ts == "mixed")),
        # domain one-hot (3)
        "domain_scientific": float(int(dom == "scientific")),
        "domain_defense": float(int(dom == "defense")),
        "domain_engineering": float(int(dom == "engineering")),
        # page stats (4)
        "num_tables": float(num_tables),
        "num_strategies_tried": float(num_strategies_tried),
        "max_fragmentation": float(max_fragmentation),
        "has_fragmentation": float(has_fragmentation),
        # detection flags (2)
        "lattice_found": float(lattice_found),
        "stream_found": float(stream_found),
        # per-strategy fragmentation scores (8), -1 = not tried
        "frag_lattice_default": float(fs.get("lattice_default", -1)),
        "frag_lattice_strong": float(fs.get("lattice_strong", -1)),
        "frag_stream_default": float(fs.get("stream_default", -1)),
        "frag_stream_tight": float(fs.get("stream_tight", -1)),
        "frag_stream_wide": float(fs.get("stream_wide", -1)),
        "frag_stream_columns": float(fs.get("stream_columns", -1)),
        "frag_agent_tuned": float(fs.get("agent_tuned", -1)),
        "frag_memory_learned": float(fs.get("memory_learned", -1)),
        # encoded category (1)
        "category": float(_CAT_ENCODER.get(category or "unknown", 0)),
    }

    # Order features to match the trained model
    if _feature_order:
        return [feature_dict.get(k, 0.0) for k in _feature_order]

    # Fallback: legacy hardcoded order (_FEATURE_COLS + category)
    return [feature_dict.get(k, 0.0) for k in _FEATURE_COLS] + [feature_dict["category"]]


def _load_classifier() -> bool:
    """Lazy-load the classifier, label encoder, and feature order. Returns True if ready."""
    global _classifier, _label_encoder, _feature_order
    if _classifier is False:
        return False
    if _classifier is not None:
        return True

    model_path = Path(_CLASSIFIER_MODEL_PATH)
    encoder_path = Path(_LABEL_ENCODER_PATH)
    metrics_path = model_path.parent / "metrics.json"

    if not model_path.exists():
        _classifier = False
        return False

    try:
        import joblib

        _classifier = joblib.load(model_path)
        if encoder_path.exists():
            _label_encoder = joblib.load(encoder_path)
        # Load feature order from metrics.json (produced by /classifier-lab)
        if metrics_path.exists():
            import json
            metrics = json.loads(metrics_path.read_text())
            _feature_order = metrics.get("feature_order")
        logger.info(f"Loaded strategy classifier from {model_path}")
        return True
    except Exception as exc:
        logger.debug(f"Failed to load strategy classifier: {exc}")
        _classifier = False
        return False


def _predict_with_classifier(feature_row: list) -> Optional[StrategyPrediction]:
    """Run prediction on a 21-element feature vector. Returns None on failure."""
    try:
        import numpy as np

        features = np.array([feature_row])
        pred_raw = _classifier.predict(features)[0]
        proba = _classifier.predict_proba(features)[0]
        confidence = float(max(proba))

        # Decode class index to strategy name
        # Supports both dict (from /classifier-lab) and sklearn LabelEncoder
        if _label_encoder is not None:
            if isinstance(_label_encoder, dict):
                strategy_name = _label_encoder.get(int(pred_raw), str(pred_raw))
            else:
                strategy_name = _label_encoder.inverse_transform([pred_raw])[0]
        else:
            strategy_name = str(pred_raw)

        return StrategyPrediction(
            strategy_name=strategy_name,
            confidence=confidence,
            tier="classifier",
        )
    except Exception as exc:
        logger.debug(f"Classifier prediction failed: {exc}")
        return None


def _tier05_classifier(
    table_style: Optional[str],
    domain: Optional[str],
    page_density: Optional[float],
    has_borders: Optional[bool],
    category: Optional[str],
) -> Optional[StrategyPrediction]:
    """Tier 0.5: Try /assistant classify first, direct joblib fallback second.

    Returns None if no model available or prediction fails.
    """
    # Try 1: /assistant cascade (if available)
    assistant_pred = _tier05_assistant(table_style, domain, has_borders, category)
    if assistant_pred is not None:
        return assistant_pred

    # Try 2: Direct joblib load (fast ~5ms fallback)
    if not _load_classifier():
        return None

    # Build 21-feature vector (pre-sweep: post-sweep features default to -1/0)
    feature_row = _build_feature_vector(
        table_style=table_style,
        domain=domain,
        category=category,
    )

    pred = _predict_with_classifier(feature_row)
    if pred is not None:
        pred.features = {
            "table_style": table_style,
            "domain": domain,
            "category": category,
            "mode": "pre_sweep",
        }
    return pred


def predict_strategy(
    table_style: Optional[str] = None,
    domain: Optional[str] = None,
    page_density: Optional[float] = None,
    has_borders: Optional[bool] = None,
    category: Optional[str] = None,
    page_image_path: Optional[str] = None,
) -> Optional[StrategyPrediction]:
    """Run the strategy selector cascade.

    Returns the highest-confidence prediction available, or None if
    STRATEGY_SELECTOR_MODE == "off".
    """
    if STRATEGY_SELECTOR_MODE == "off":
        return None

    # Tier 0.5: classifier (if available, takes priority over heuristic)
    cls_pred = _tier05_classifier(
        table_style, domain, page_density, has_borders, category
    )
    if cls_pred is not None and cls_pred.confidence >= 0.70:
        return cls_pred

    # Tier 0: heuristic (always available)
    return _tier0_heuristic(table_style, domain, has_borders)


def confirm_strategy(
    table_style: Optional[str] = None,
    domain: Optional[str] = None,
    category: Optional[str] = None,
    strategies_tried: Optional[List[str]] = None,
    frag_scores: Optional[Dict[str, int]] = None,
    lattice_found: int = 0,
    stream_found: int = 0,
) -> Optional[StrategyPrediction]:
    """Post-sweep classifier confirmation with ALL 21 features populated.

    This is the high-accuracy path (F1=0.99) since all features are available
    after the brute-force sweep. Returns None if classifier unavailable.
    """
    if not _load_classifier():
        return None

    fs = frag_scores or {}
    tried = strategies_tried or []
    max_frag = max(fs.values(), default=0)

    feature_row = _build_feature_vector(
        table_style=table_style,
        domain=domain,
        category=category,
        num_tables=1,
        num_strategies_tried=len(tried),
        max_fragmentation=max_frag,
        has_fragmentation=int(max_frag > 0),
        lattice_found=lattice_found,
        stream_found=stream_found,
        frag_scores=fs,
    )

    pred = _predict_with_classifier(feature_row)
    if pred is not None:
        pred.features = {
            "table_style": table_style,
            "domain": domain,
            "category": category,
            "strategies_tried": tried,
            "mode": "post_sweep",
        }
    return pred


def log_disagreement(
    page_num: int,
    predicted: Optional[StrategyPrediction],
    actual_best: Optional[str],
    strategies_tried: List[str],
    frag_scores: Dict[str, int],
    output_dir: Path,
    s00_table_style: Optional[str] = None,
    s00_domain: Optional[str] = None,
    category: Optional[str] = None,
    page_stats: Optional[Dict] = None,
    actual_flavor: Optional[str] = None,
) -> None:
    """Append a strategy outcome record to 05_strategy_outcomes.jsonl.

    Always writes (even if prediction == actual) so the downstream
    classifier gets positive examples too.
    """
    # Post-sweep classifier confirmation (shadow mode only — log, don't override)
    confirmation = confirm_strategy(
        table_style=s00_table_style,
        domain=s00_domain,
        category=category,
        strategies_tried=strategies_tried,
        frag_scores=frag_scores,
        lattice_found=sum(1 for s in strategies_tried if s.startswith("lattice")),
        stream_found=sum(1 for s in strategies_tried if s.startswith("stream")),
    )
    if confirmation and confirmation.confidence >= 0.90 and actual_best:
        if confirmation.strategy_name != actual_best:
            logger.debug(
                f"Page {page_num}: classifier_override candidate — "
                f"classifier={confirmation.strategy_name} "
                f"(conf={confirmation.confidence:.2f}) vs sweep={actual_best}"
            )

    record = {
        "page_num": page_num,
        "predicted_strategy": predicted.strategy_name if predicted else None,
        "predicted_confidence": round(predicted.confidence, 3) if predicted else None,
        "predicted_tier": predicted.tier if predicted else None,
        "confirmed_strategy": confirmation.strategy_name if confirmation else None,
        "confirmed_confidence": round(confirmation.confidence, 3) if confirmation else None,
        "actual_best": actual_best,
        "actual_flavor": actual_flavor,
        "strategies_tried": strategies_tried,
        "fragmentation_scores": frag_scores,
        "s00_table_style": s00_table_style,
        "s00_domain": s00_domain,
        "category": category,
    }
    if page_stats:
        record["page_stats"] = page_stats

    outcomes_path = output_dir / "05_strategy_outcomes.jsonl"
    try:
        with open(outcomes_path, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.debug(f"Failed to write strategy outcome: {exc}")


def should_skip_sweep(prediction: Optional[StrategyPrediction]) -> bool:
    """In active mode, determine if we can skip the full strategy sweep.

    Returns True only when:
    - STRATEGY_SELECTOR_MODE == "active"
    - prediction confidence >= threshold
    """
    if STRATEGY_SELECTOR_MODE != "active":
        return False
    if prediction is None:
        return False
    return prediction.confidence >= _ACTIVE_CONFIDENCE_THRESHOLD
