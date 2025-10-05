#!/usr/bin/env python3
"""
Unit tests for confidence composition utilities.
"""

import pytest
from extractor.pipeline.utils.confidence import (
    compose_confidence,
    merge_confidence_components,
    confidence_report,
)


def test_compose_confidence_all_components():
    """Test composing confidence with all components provided."""
    result = compose_confidence(
        structure_prob=0.8,
        heading_factor=0.9,
        numeric_recall=0.85,
        hallucination_factor=0.95,
    )
    
    assert result["count"] == 4
    assert result["method"] == "geometric_mean"
    assert 0.8 < result["score"] < 0.9  # Geometric mean of [0.8, 0.9, 0.85, 0.95]
    assert result["components"]["structure_prob"] == 0.8
    assert result["components"]["heading_factor"] == 0.9


def test_compose_confidence_partial_components():
    """Test composing confidence with some None values."""
    result = compose_confidence(
        structure_prob=0.8,
        heading_factor=0.9,
        numeric_recall=None,
        hallucination_factor=None,
    )
    
    assert result["count"] == 2
    assert result["score"] is not None
    # Geometric mean of 0.8 and 0.9: sqrt(0.8 * 0.9) ≈ 0.8485
    assert abs(result["score"] - 0.8485) < 0.01


def test_compose_confidence_all_none():
    """Test composing confidence when all components are None."""
    result = compose_confidence(
        structure_prob=None,
        heading_factor=None,
        numeric_recall=None,
        hallucination_factor=None,
    )
    
    assert result["count"] == 0
    assert result["score"] is None
    assert result["method"] == "geometric_mean"


def test_compose_confidence_single_component():
    """Test composing confidence with single component."""
    result = compose_confidence(
        structure_prob=0.75,
        heading_factor=None,
        numeric_recall=None,
        hallucination_factor=None,
    )
    
    assert result["count"] == 1
    assert result["score"] == 0.75  # Geometric mean of single value is itself


def test_compose_confidence_extra_components():
    """Test composing confidence with extra keyword arguments."""
    result = compose_confidence(
        structure_prob=0.8,
        table_quality=0.9,
        ocr_confidence=0.85,
    )
    
    assert result["count"] == 3
    assert "table_quality" in result["components"]
    assert "ocr_confidence" in result["components"]


def test_merge_confidence_components_new():
    """Test merging new components into None base."""
    result = merge_confidence_components(
        None,
        {"structure_prob": 0.8, "heading_factor": 0.9}
    )
    
    assert result["count"] == 2
    assert result["components"]["structure_prob"] == 0.8
    assert result["components"]["heading_factor"] == 0.9


def test_merge_confidence_components_update():
    """Test updating existing confidence with new components."""
    base = compose_confidence(structure_prob=0.8)
    result = merge_confidence_components(
        base,
        {"heading_factor": 0.9, "numeric_recall": 0.85}
    )
    
    assert result["count"] == 3
    assert result["components"]["structure_prob"] == 0.8
    assert result["components"]["heading_factor"] == 0.9
    assert result["components"]["numeric_recall"] == 0.85


def test_merge_confidence_components_override():
    """Test overriding existing component values."""
    base = compose_confidence(structure_prob=0.7, heading_factor=0.8)
    result = merge_confidence_components(
        base,
        {"heading_factor": 0.9}  # Override
    )
    
    assert result["components"]["structure_prob"] == 0.7
    assert result["components"]["heading_factor"] == 0.9  # Updated


def test_confidence_report_full():
    """Test generating report with full confidence."""
    conf = compose_confidence(
        structure_prob=0.85,
        heading_factor=0.92,
    )
    
    report = confidence_report(conf)
    
    assert "Confidence: 0.88" in report
    assert "2 components" in report
    assert "structure_prob: 0.85" in report
    assert "heading_factor: 0.92" in report


def test_confidence_report_none():
    """Test generating report with None confidence."""
    report = confidence_report(None)
    assert "Confidence: None" in report


def test_confidence_report_partial():
    """Test generating report with partial components."""
    conf = compose_confidence(
        structure_prob=0.8,
        heading_factor=None,
        numeric_recall=0.9,
    )
    
    report = confidence_report(conf)
    
    assert "2 components" in report
    assert "structure_prob: 0.8" in report
    assert "heading_factor: None" in report
    assert "numeric_recall: 0.9" in report


def test_geometric_mean_property():
    """Test that geometric mean is more sensitive to low values than arithmetic."""
    # With one low value, geometric mean should be lower than arithmetic
    conf = compose_confidence(
        structure_prob=0.9,
        heading_factor=0.9,
        numeric_recall=0.5,  # Low value
    )
    
    # Geometric mean: (0.9 * 0.9 * 0.5)^(1/3) ≈ 0.741
    # Arithmetic mean: (0.9 + 0.9 + 0.5) / 3 ≈ 0.767
    assert conf["score"] < 0.767
    assert abs(conf["score"] - 0.741) < 0.01
