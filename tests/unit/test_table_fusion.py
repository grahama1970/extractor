#!/usr/bin/env python3
"""
Unit tests for table fusion module.
"""

import pytest
import tempfile
import pickle
import os
from extractor.pipeline.utils.table_fusion import (
    TableCandidate,
    fuse_table_candidates,
)


def test_fuse_single_candidate():
    """Test fusion with single candidate (no-op pass-through)."""
    candidate = TableCandidate(
        pandas_df=[{"col1": "A", "col2": "B"}, {"col1": "C", "col2": "D"}],
        bbox=[100, 200, 500, 300],
        page_index=0,
        strategy="lattice",
        score=85.0,
        fragmentation_score=0.12,
        camelot_metrics={"accuracy": 92.5, "whitespace": 8.3},
        pandas_metrics={"shape": [2, 2], "data_density": 0.95},
    )
    
    result = fuse_table_candidates([candidate])
    
    assert result["merge_type"] == "single"
    assert result["pandas_df"] == candidate.pandas_df
    assert result["bbox"] == candidate.bbox
    assert result["page_index"] == 0
    assert result["source_strategies"] == ["lattice"]
    
    # Check confidence components exist
    assert "confidence" in result
    conf = result["confidence"]
    assert "fragmentation" in conf
    assert "header_jaccard" in conf
    assert "numeric_stability" in conf


def test_fuse_empty_candidates():
    """Test fusion with empty candidate list."""
    result = fuse_table_candidates([])
    
    assert result["merge_type"] == "empty"
    assert result["pandas_df"] == []
    assert result["source_strategies"] == []


def test_fuse_header_body_merge():
    """Test fusion detects and merges header+body split tables."""
    # Header candidate: single row
    header = TableCandidate(
        pandas_df=[{"Signal": "valid_i", "IO": "I", "Type": "input"}],
        bbox=[100, 100, 500, 120],
        page_index=0,
        strategy="lattice",
        score=80.0,
        fragmentation_score=0.05,
    )
    
    # Body candidate: multiple rows, similar horizontal position
    body = TableCandidate(
        pandas_df=[
            {"col1": "reset_i", "col2": "I", "col3": "reset"},
            {"col1": "clk_i", "col2": "I", "col3": "clock"},
        ],
        bbox=[100, 150, 500, 200],
        page_index=0,
        strategy="lattice",
        score=90.0,
        fragmentation_score=0.08,
    )
    
    result = fuse_table_candidates([header, body])
    
    # Should detect header+body pattern and merge
    assert result["merge_type"] == "header_body_merge"
    
    # Merged table should have 3 rows (1 header + 2 body)
    assert len(result["pandas_df"]) == 3
    
    # First row should be from header
    assert result["pandas_df"][0] == header.pandas_df[0]


def test_fuse_multi_candidate_best_selection():
    """Test fusion selects best from multiple candidates."""
    candidates = [
        TableCandidate(
            pandas_df=[{"col1": "A"}],
            bbox=[100, 100, 200, 150],
            page_index=0,
            strategy="lattice",
            score=70.0,
            fragmentation_score=0.2,
            pandas_metrics={"data_density": 0.5},
        ),
        TableCandidate(
            pandas_df=[{"col1": "B"}],
            bbox=[100, 100, 200, 150],
            page_index=0,
            strategy="stream",
            score=90.0,  # Higher score
            fragmentation_score=0.1,
            pandas_metrics={"data_density": 0.9},
        ),
        TableCandidate(
            pandas_df=[{"col1": "C"}],
            bbox=[100, 100, 200, 150],
            page_index=0,
            strategy="network",
            score=75.0,
            fragmentation_score=0.15,
            pandas_metrics={"data_density": 0.7},
        ),
    ]
    
    result = fuse_table_candidates(candidates)
    
    assert result["merge_type"] == "multi_best"
    # Should select the candidate with score=90.0
    assert result["pandas_df"] == [{"col1": "B"}]
    
    # Should track all strategies
    assert len(result["source_strategies"]) == 3
    assert "lattice" in result["source_strategies"]
    assert "stream" in result["source_strategies"]
    assert "network" in result["source_strategies"]


def test_header_body_no_merge_different_pages():
    """Test header+body NOT merged if pages too far apart."""
    header = TableCandidate(
        pandas_df=[{"col1": "Header"}],
        bbox=[100, 100, 500, 120],
        page_index=0,
        strategy="lattice",
        score=80.0,
        fragmentation_score=0.05,
    )
    
    body = TableCandidate(
        pandas_df=[{"col1": "Row1"}, {"col1": "Row2"}],
        bbox=[100, 150, 500, 200],
        page_index=3,  # Too far from page 0
        strategy="lattice",
        score=90.0,
        fragmentation_score=0.08,
    )
    
    result = fuse_table_candidates([header, body])
    
    # Should NOT merge due to page distance
    assert result["merge_type"] != "header_body_merge"
    # Should fall back to multi_best
    assert result["merge_type"] == "multi_best"


def test_header_body_no_merge_no_overlap():
    """Test header+body NOT merged if horizontal alignment poor."""
    header = TableCandidate(
        pandas_df=[{"col1": "Header"}],
        bbox=[100, 100, 300, 120],  # Left side
        page_index=0,
        strategy="lattice",
        score=80.0,
        fragmentation_score=0.05,
    )
    
    body = TableCandidate(
        pandas_df=[{"col1": "Row1"}, {"col1": "Row2"}],
        bbox=[400, 150, 600, 200],  # Right side, no overlap
        page_index=0,
        strategy="lattice",
        score=90.0,
        fragmentation_score=0.08,
    )
    
    result = fuse_table_candidates([header, body])
    
    # Should NOT merge due to poor horizontal alignment
    assert result["merge_type"] != "header_body_merge"


def test_confidence_components_structure():
    """Test confidence components have expected structure."""
    candidate = TableCandidate(
        pandas_df=[{"col1": "A", "col2": "B"}],
        bbox=[100, 200, 500, 300],
        page_index=0,
        strategy="lattice",
        score=85.0,
        fragmentation_score=0.12,
    )
    
    result = fuse_table_candidates([candidate])
    conf = result["confidence"]
    
    # Check all expected components
    assert "structure_prob" in conf
    assert "fragmentation" in conf
    assert "header_jaccard" in conf
    assert "numeric_stability" in conf
    assert "strategy_diversity" in conf
    
    # structure_prob should be None without calibrator
    assert conf["structure_prob"] is None
    
    # Other metrics should be computed
    assert isinstance(conf["fragmentation"], float)
    assert 0 <= conf["fragmentation"] <= 1
    
    assert isinstance(conf["strategy_diversity"], int)
    assert conf["strategy_diversity"] == 1  # Single strategy


def test_confidence_fragmentation_inverted():
    """Test fragmentation confidence is inverted (lower frag = higher confidence)."""
    low_frag = TableCandidate(
        pandas_df=[{"col1": "A"}],
        bbox=[100, 100, 200, 150],
        page_index=0,
        strategy="lattice",
        score=80.0,
        fragmentation_score=0.1,  # Low fragmentation
    )
    
    result_low = fuse_table_candidates([low_frag])
    conf_low = result_low["confidence"]["fragmentation"]
    
    high_frag = TableCandidate(
        pandas_df=[{"col1": "A"}],
        bbox=[100, 100, 200, 150],
        page_index=0,
        strategy="lattice",
        score=80.0,
        fragmentation_score=0.8,  # High fragmentation
    )
    
    result_high = fuse_table_candidates([high_frag])
    conf_high = result_high["confidence"]["fragmentation"]
    
    # Lower fragmentation should yield higher confidence
    assert conf_low > conf_high


def test_confidence_header_jaccard_multiple():
    """Test header Jaccard similarity with multiple candidates."""
    # Two candidates with similar headers
    cand1 = TableCandidate(
        pandas_df=[
            {"Signal": "A", "IO": "I", "Type": "input"},
            {"Signal": "B", "IO": "O", "Type": "output"},
        ],
        bbox=[100, 100, 200, 150],
        page_index=0,
        strategy="lattice",
        score=80.0,
        fragmentation_score=0.1,
    )
    
    cand2 = TableCandidate(
        pandas_df=[
            {"Signal": "C", "IO": "I", "Type": "input"},
            {"Signal": "D", "IO": "O", "Type": "output"},
        ],
        bbox=[100, 100, 200, 150],
        page_index=0,
        strategy="stream",
        score=85.0,
        fragmentation_score=0.1,
    )
    
    result = fuse_table_candidates([cand1, cand2])
    
    # Both have same column structure: Signal, IO, Type
    # Jaccard should be 1.0 (perfect match)
    assert result["confidence"]["header_jaccard"] == 1.0


def test_confidence_strategy_diversity():
    """Test strategy diversity counting."""
    candidates = [
        TableCandidate(
            pandas_df=[{"col1": "A"}],
            bbox=[100, 100, 200, 150],
            page_index=0,
            strategy="lattice",
            score=80.0,
            fragmentation_score=0.1,
        ),
        TableCandidate(
            pandas_df=[{"col1": "B"}],
            bbox=[100, 100, 200, 150],
            page_index=0,
            strategy="stream",
            score=85.0,
            fragmentation_score=0.1,
        ),
        TableCandidate(
            pandas_df=[{"col1": "C"}],
            bbox=[100, 100, 200, 150],
            page_index=0,
            strategy="lattice",  # Duplicate
            score=82.0,
            fragmentation_score=0.1,
        ),
    ]
    
    result = fuse_table_candidates(candidates)
    
    # 2 unique strategies: lattice, stream
    assert result["confidence"]["strategy_diversity"] == 2


def test_calibrator_loading_nonexistent():
    """Test graceful handling of nonexistent calibrator."""
    candidate = TableCandidate(
        pandas_df=[{"col1": "A"}],
        bbox=[100, 100, 200, 150],
        page_index=0,
        strategy="lattice",
        score=80.0,
        fragmentation_score=0.1,
    )
    
    # Pass nonexistent path
    result = fuse_table_candidates([candidate], calibrator_path="/nonexistent/model.pkl")
    
    # Should not crash, structure_prob should be None
    assert result["confidence"]["structure_prob"] is None


def test_backward_compatibility_fields():
    """Test that result contains backward-compatible fields."""
    candidate = TableCandidate(
        pandas_df=[{"col1": "A", "col2": "B"}],
        bbox=[100, 200, 500, 300],
        page_index=0,
        strategy="lattice",
        score=85.0,
        fragmentation_score=0.12,
        camelot_metrics={"accuracy": 92.5, "whitespace": 8.3},
        pandas_metrics={"shape": [1, 2], "data_density": 0.95},
    )
    
    result = fuse_table_candidates([candidate])
    
    # Legacy fields that downstream consumers expect
    assert "pandas_df" in result
    assert "bbox" in result
    assert "page_index" in result
    assert "camelot_metrics" in result
    assert "pandas_metrics" in result
    
    # New fields are additive
    assert "confidence" in result
    assert "merge_type" in result
    assert "source_strategies" in result
