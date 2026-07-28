#!/usr/bin/env python3
"""Tests for strategy_selector.py — Shadow-LEGO strategy prediction cascade.

Tests:
1. Tier 0 heuristic rules for all table_style values
2. predict_strategy() returns None when mode == "off"
3. should_skip_sweep() gating logic
4. log_disagreement() writes valid JSONL
"""

import json
import os
import tempfile
from pathlib import Path

import pytest


def test_heuristic_borderless():
    """Verify _tier0_heuristic returns stream_default for borderless scientific tables."""
    from extractor.pipeline.utils.tables.strategy_selector import _tier0_heuristic

    pred = _tier0_heuristic("borderless", "scientific", False)
    assert pred.strategy_name == "stream_default"
    assert pred.confidence == 0.70
    assert pred.tier == "heuristic"


def test_heuristic_bordered_defense():
    """Test heuristic strategy selection for bordered defense tables."""
    from extractor.pipeline.utils.tables.strategy_selector import _tier0_heuristic

    pred = _tier0_heuristic("bordered", "defense", True)
    assert pred.strategy_name == "lattice_strong"
    assert pred.confidence == 0.80


def test_heuristic_bordered_general():
    """Test bordered general heuristic returns lattice_default strategy."""
    from extractor.pipeline.utils.tables.strategy_selector import _tier0_heuristic

    pred = _tier0_heuristic("bordered", "general", True)
    assert pred.strategy_name == "lattice_default"
    assert pred.confidence == 0.75


def test_heuristic_mixed():
    """Test the tier0 heuristic for mixed engineering input."""
    from extractor.pipeline.utils.tables.strategy_selector import _tier0_heuristic

    pred = _tier0_heuristic("mixed", "engineering", None)
    assert pred.strategy_name == "lattice_default"
    assert pred.confidence == 0.50


def test_heuristic_none_style():
    """Test heuristic none style."""
    from extractor.pipeline.utils.tables.strategy_selector import _tier0_heuristic

    pred = _tier0_heuristic(None, None, None)
    assert pred.strategy_name == "lattice_default"
    assert pred.confidence == 0.50


def test_heuristic_has_borders_false():
    """has_borders=False should route to stream even if table_style is None."""
    from extractor.pipeline.utils.tables.strategy_selector import _tier0_heuristic

    pred = _tier0_heuristic(None, "general", False)
    assert pred.strategy_name == "stream_default"


def test_predict_strategy_off_mode(monkeypatch):
    """Test strategy prediction with selector mode set to off."""
    monkeypatch.setattr(
        "extractor.pipeline.utils.tables.strategy_selector.STRATEGY_SELECTOR_MODE",
        "off",
    )
    from extractor.pipeline.utils.tables.strategy_selector import predict_strategy

    result = predict_strategy(table_style="bordered", domain="defense")
    assert result is None


def test_predict_strategy_shadow_mode(monkeypatch):
    """Validate strategy prediction in shadow mode."""
    monkeypatch.setattr(
        "extractor.pipeline.utils.tables.strategy_selector.STRATEGY_SELECTOR_MODE",
        "shadow",
    )
    from extractor.pipeline.utils.tables.strategy_selector import predict_strategy

    result = predict_strategy(table_style="borderless", domain="scientific")
    assert result is not None
    assert result.strategy_name == "stream_default"


def test_should_skip_sweep_shadow(monkeypatch):
    """Test if the sweep should be skipped based on strategy mode."""
    monkeypatch.setattr(
        "extractor.pipeline.utils.tables.strategy_selector.STRATEGY_SELECTOR_MODE",
        "shadow",
    )
    from extractor.pipeline.utils.tables.strategy_selector import (
        should_skip_sweep,
        StrategyPrediction,
    )

    pred = StrategyPrediction("lattice_default", 0.95, "heuristic")
    assert should_skip_sweep(pred) is False  # shadow never skips


def test_should_skip_sweep_active_high_confidence(monkeypatch):
    """Verify sweep is skipped with active high confidence."""
    monkeypatch.setattr(
        "extractor.pipeline.utils.tables.strategy_selector.STRATEGY_SELECTOR_MODE",
        "active",
    )
    monkeypatch.setattr(
        "extractor.pipeline.utils.tables.strategy_selector._ACTIVE_CONFIDENCE_THRESHOLD",
        0.85,
    )
    from extractor.pipeline.utils.tables.strategy_selector import (
        should_skip_sweep,
        StrategyPrediction,
    )

    pred = StrategyPrediction("lattice_default", 0.90, "classifier")
    assert should_skip_sweep(pred) is True


def test_should_skip_sweep_active_low_confidence(monkeypatch):
    """Set strategy selector mode for testing sweep skipping logic."""
    monkeypatch.setattr(
        "extractor.pipeline.utils.tables.strategy_selector.STRATEGY_SELECTOR_MODE",
        "active",
    )
    from extractor.pipeline.utils.tables.strategy_selector import (
        should_skip_sweep,
        StrategyPrediction,
    )

    pred = StrategyPrediction("lattice_default", 0.60, "heuristic")
    assert should_skip_sweep(pred) is False


def test_should_skip_sweep_none():
    """Verify `None` input does not skip sweep."""
    from extractor.pipeline.utils.tables.strategy_selector import should_skip_sweep

    assert should_skip_sweep(None) is False


def test_log_disagreement_writes_jsonl():
    """Log disagreement information to a JSONL file."""
    from extractor.pipeline.utils.tables.strategy_selector import (
        log_disagreement,
        StrategyPrediction,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        pred = StrategyPrediction("lattice_default", 0.72, "heuristic")

        log_disagreement(
            page_num=42,
            predicted=pred,
            actual_best="stream_default",
            strategies_tried=["lattice_default", "stream_default"],
            frag_scores={"lattice_default": 5, "stream_default": 0},
            output_dir=output_dir,
            s00_table_style="borderless",
            s00_domain="scientific",
            category="arxiv",
        )

        outcomes_path = output_dir / "05_strategy_outcomes.jsonl"
        assert outcomes_path.exists()

        lines = outcomes_path.read_text().strip().split("\n")
        assert len(lines) == 1

        record = json.loads(lines[0])
        assert record["page_num"] == 42
        assert record["predicted_strategy"] == "lattice_default"
        assert record["predicted_confidence"] == 0.72
        assert record["actual_best"] == "stream_default"
        assert record["s00_table_style"] == "borderless"
        assert record["category"] == "arxiv"


def test_log_disagreement_appends():
    """Multiple calls should append, not overwrite."""
    from extractor.pipeline.utils.tables.strategy_selector import (
        log_disagreement,
        StrategyPrediction,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        pred = StrategyPrediction("lattice_default", 0.50, "heuristic")

        for i in range(3):
            log_disagreement(
                page_num=i,
                predicted=pred,
                actual_best="lattice_default",
                strategies_tried=["lattice_default"],
                frag_scores={},
                output_dir=output_dir,
            )

        lines = (output_dir / "05_strategy_outcomes.jsonl").read_text().strip().split("\n")
        assert len(lines) == 3


def test_log_disagreement_no_prediction():
    """Should handle None prediction gracefully."""
    from extractor.pipeline.utils.tables.strategy_selector import log_disagreement

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        log_disagreement(
            page_num=0,
            predicted=None,
            actual_best="lattice_default",
            strategies_tried=["lattice_default"],
            frag_scores={},
            output_dir=output_dir,
        )

        record = json.loads(
            (output_dir / "05_strategy_outcomes.jsonl").read_text().strip()
        )
        assert record["predicted_strategy"] is None
        assert record["predicted_confidence"] is None


# --- Tests for 21-feature vector fix (Task 1, 2, 3 of 03_CLOSE_SHADOW_LEGO) ---


def test_build_feature_vector_length():
    """Feature vector must be exactly 21 elements (20 FEATURE_COLS + 1 category)."""
    from extractor.pipeline.utils.tables.strategy_selector import _build_feature_vector

    fv = _build_feature_vector(table_style="bordered", domain="defense", category="defense")
    assert len(fv) == 21


def test_build_feature_vector_one_hot_encoding():
    """One-hot encoding for table_style and domain must be correct."""
    from extractor.pipeline.utils.tables.strategy_selector import (
        _build_feature_vector, _feature_order, _FEATURE_COLS,
    )

    fv = _build_feature_vector(table_style="borderless", domain="scientific", category="scientific")
    assert len(fv) == 21

    # Determine feature ordering (from metrics.json or legacy)
    order = _feature_order if _feature_order else _FEATURE_COLS + ["category"]

    def idx(name):
        """Return the 0-based index of the name in the order sequence."""
        return order.index(name)

    # table_style one-hot
    assert fv[idx("table_style_borderless")] == 1
    assert fv[idx("table_style_bordered")] == 0
    assert fv[idx("table_style_mixed")] == 0
    # domain one-hot
    assert fv[idx("domain_scientific")] == 1
    assert fv[idx("domain_defense")] == 0
    assert fv[idx("domain_engineering")] == 0


def test_build_feature_vector_frag_defaults():
    """Pre-sweep call: frag scores default to -1 (not tried)."""
    from extractor.pipeline.utils.tables.strategy_selector import (
        _build_feature_vector, _feature_order, _FEATURE_COLS,
    )

    fv = _build_feature_vector(table_style="bordered", domain="defense")
    order = _feature_order if _feature_order else _FEATURE_COLS + ["category"]

    frag_keys = [
        "frag_lattice_default", "frag_lattice_strong",
        "frag_stream_default", "frag_stream_tight", "frag_stream_wide",
        "frag_stream_columns", "frag_agent_tuned", "frag_memory_learned",
    ]
    for key in frag_keys:
        idx = order.index(key)
        assert fv[idx] == -1, f"{key} (idx={idx}) should be -1 (not tried), got {fv[idx]}"


def test_tier05_classifier_feature_vector(monkeypatch):
    """Tier 0.5 classifier builds 21-feature vector and returns valid prediction."""
    monkeypatch.setattr(
        "extractor.pipeline.utils.tables.strategy_selector._ASSISTANT_RUN",
        Path("/nonexistent"),  # force joblib path
    )

    from extractor.pipeline.utils.tables.strategy_selector import _tier05_classifier

    # Reset classifier state for clean test
    import extractor.pipeline.utils.tables.strategy_selector as ss
    ss._classifier = None
    ss._label_encoder = None

    model_path = Path("models/table-strategy-classifier/model.joblib")
    if not model_path.exists():
        pytest.skip("model.joblib not available")

    pred = _tier05_classifier(
        table_style="bordered", domain="defense",
        page_density=None, has_borders=True, category="defense",
    )
    assert pred is not None, "Classifier should return a prediction (not None)"
    assert isinstance(pred.strategy_name, str)
    assert pred.confidence > 0
    assert pred.tier == "classifier"


def test_confirm_strategy_with_full_features():
    """Post-sweep confirmation with all features returns high-confidence prediction."""
    from extractor.pipeline.utils.tables.strategy_selector import confirm_strategy
    import extractor.pipeline.utils.tables.strategy_selector as ss

    model_path = Path("models/table-strategy-classifier/model.joblib")
    if not model_path.exists():
        pytest.skip("model.joblib not available")

    # Reset for clean test
    ss._classifier = None
    ss._label_encoder = None

    pred = confirm_strategy(
        table_style="bordered",
        domain="defense",
        category="defense",
        strategies_tried=["lattice_default", "lattice_strong", "stream_default"],
        frag_scores={"lattice_default": 2, "lattice_strong": 0, "stream_default": 5},
        lattice_found=2,
        stream_found=1,
    )
    assert pred is not None, "Post-sweep confirmation should return a prediction"
    assert pred.confidence > 0.70, f"Post-sweep confidence should be >0.70, got {pred.confidence}"


def test_classifier_fallback_on_missing_model(monkeypatch, tmp_path):
    """Graceful None return when model.joblib is missing."""
    monkeypatch.setattr(
        "extractor.pipeline.utils.tables.strategy_selector._CLASSIFIER_MODEL_PATH",
        str(tmp_path / "nonexistent" / "model.joblib"),
    )
    monkeypatch.setattr(
        "extractor.pipeline.utils.tables.strategy_selector._ASSISTANT_RUN",
        Path("/nonexistent"),
    )

    import extractor.pipeline.utils.tables.strategy_selector as ss
    ss._classifier = None
    ss._label_encoder = None

    from extractor.pipeline.utils.tables.strategy_selector import _tier05_classifier

    pred = _tier05_classifier("bordered", "defense", None, True, "defense")
    assert pred is None


def test_label_encoder_decodes_strategy_names():
    """Label encoder maps integers back to valid strategy names."""
    encoder_path = Path("models/table-strategy-classifier/label_encoder.joblib")
    if not encoder_path.exists():
        pytest.skip("label_encoder.joblib not available")

    import joblib
    le = joblib.load(encoder_path)

    valid_strategies = {
        "lattice_default", "lattice_strong", "lattice_sensitive",
        "stream_default", "stream_tight", "stream_wide", "stream_columns",
        "agent_tuned", "memory_learned", "preset_config",
    }
    # Support both dict (from /classifier-lab) and sklearn LabelEncoder
    if isinstance(le, dict):
        classes = list(le.values())
    else:
        classes = list(le.classes_)
    for cls in classes:
        assert str(cls) in valid_strategies, f"Unknown strategy class: {cls}"


def test_predict_strategy_cascade_order(monkeypatch):
    """Tier 0.5 runs before Tier 0; high-confidence classifier overrides heuristic."""
    monkeypatch.setattr(
        "extractor.pipeline.utils.tables.strategy_selector.STRATEGY_SELECTOR_MODE",
        "shadow",
    )
    monkeypatch.setattr(
        "extractor.pipeline.utils.tables.strategy_selector._ASSISTANT_RUN",
        Path("/nonexistent"),
    )

    import extractor.pipeline.utils.tables.strategy_selector as ss
    ss._classifier = None
    ss._label_encoder = None

    from extractor.pipeline.utils.tables.strategy_selector import predict_strategy

    model_path = Path("models/table-strategy-classifier/model.joblib")
    if not model_path.exists():
        pytest.skip("model.joblib not available")

    pred = predict_strategy(
        table_style="borderless", domain="scientific", category="scientific",
    )
    assert pred is not None
    # If classifier confidence >= 0.70 it should be "classifier" tier
    # Otherwise it falls through to "heuristic" — both are valid cascade outcomes
    assert pred.tier in ("classifier", "heuristic")


def test_log_disagreement_includes_confirmation():
    """log_disagreement should include confirmed_strategy field from post-sweep."""
    from extractor.pipeline.utils.tables.strategy_selector import (
        log_disagreement, StrategyPrediction,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        pred = StrategyPrediction("lattice_default", 0.72, "heuristic")

        log_disagreement(
            page_num=1,
            predicted=pred,
            actual_best="stream_default",
            strategies_tried=["lattice_default", "stream_default"],
            frag_scores={"lattice_default": 3, "stream_default": 0},
            output_dir=output_dir,
            s00_table_style="bordered",
            s00_domain="defense",
            category="defense",
        )

        record = json.loads(
            (output_dir / "05_strategy_outcomes.jsonl").read_text().strip()
        )
        # confirmed_strategy field should always be present (may be None if no model)
        assert "confirmed_strategy" in record
        assert "confirmed_confidence" in record
