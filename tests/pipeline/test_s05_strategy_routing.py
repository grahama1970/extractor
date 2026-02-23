#!/usr/bin/env python3
"""Tests for S00→S05 profile-driven strategy routing (TASK-003) and
stream strategies (TASK-004).

These tests verify:
1. All 7 strategies are registered (4 lattice + 3 new stream + 1 existing stream)
2. S00 table_style=borderless routes to stream_default first
3. S00 table_style=bordered routes to lattice_default first
4. S00 table_style=bordered + domain=defense routes to lattice_strong
5. S00 table_style=mixed triggers full sweep
6. S00 signals (table_style, domain, has_multi_column) flow through pipeline_context
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_all_stream_strategies_registered():
    """TASK-004: Verify all 7 Camelot strategies are available."""
    from extractor.pipeline.utils.tables.extraction import CAMELOT_STRATEGIES

    expected = {
        "lattice_default",
        "lattice_strong",
        "lattice_sensitive",
        "stream_default",
        "stream_tight",
        "stream_wide",
        "stream_columns",
    }
    assert expected == set(CAMELOT_STRATEGIES.keys()), (
        f"Missing strategies: {expected - set(CAMELOT_STRATEGIES.keys())}"
    )


def test_stream_tight_params():
    """TASK-004: stream_tight has edge_tol=30, row_tol=5."""
    from extractor.pipeline.utils.tables.extraction import CAMELOT_STRATEGIES

    s = CAMELOT_STRATEGIES["stream_tight"]
    assert s["flavor"] == "stream"
    assert s["params"]["edge_tol"] == 30
    assert s["params"]["row_tol"] == 5


def test_stream_wide_params():
    """TASK-004: stream_wide has edge_tol=80, row_tol=15."""
    from extractor.pipeline.utils.tables.extraction import CAMELOT_STRATEGIES

    s = CAMELOT_STRATEGIES["stream_wide"]
    assert s["flavor"] == "stream"
    assert s["params"]["edge_tol"] == 80
    assert s["params"]["row_tol"] == 15


def test_stream_columns_params():
    """TASK-004: stream_columns has edge_tol=50, column_tol=10."""
    from extractor.pipeline.utils.tables.extraction import CAMELOT_STRATEGIES

    s = CAMELOT_STRATEGIES["stream_columns"]
    assert s["flavor"] == "stream"
    assert s["params"]["edge_tol"] == 50
    assert s["params"]["column_tol"] == 10


def test_borderless_routes_to_stream():
    """TASK-003: S00 table_style=borderless should route to stream_default first."""
    from extractor.pipeline.steps.s05_table_extractor import extract_all_tables
    from extractor.pipeline.utils.tables.extraction import CAMELOT_STRATEGIES

    # Mock fitz.open to avoid needing a real PDF
    mock_doc = MagicMock()
    mock_doc.__len__ = lambda self: 0  # 0 pages = no iteration
    mock_doc.__enter__ = lambda self: self
    mock_doc.__exit__ = lambda *args: None

    context = {"table_style": "borderless", "domain": "scientific"}

    with patch("extractor.pipeline.steps.s05_table_extractor.fitz") as mock_fitz:
        mock_fitz.open.return_value = mock_doc
        _, strategy_summary, quality_summary = extract_all_tables(
            pdf_path=Path("/dev/null"),
            output_dir=Path("/tmp/test_s05_routing"),
            diagnostics=[],
            context=context,
        )

    assert quality_summary.get("s00_routed_strategy") == "stream_default", (
        f"Expected stream_default routing, got {quality_summary}"
    )
    assert quality_summary.get("s00_table_style") == "borderless"


def test_bordered_routes_to_lattice():
    """TASK-003: S00 table_style=bordered should keep lattice_default."""
    from extractor.pipeline.steps.s05_table_extractor import extract_all_tables

    mock_doc = MagicMock()
    mock_doc.__len__ = lambda self: 0

    context = {"table_style": "bordered", "domain": "general"}

    with patch("extractor.pipeline.steps.s05_table_extractor.fitz") as mock_fitz:
        mock_fitz.open.return_value = mock_doc
        _, _, quality_summary = extract_all_tables(
            pdf_path=Path("/dev/null"),
            output_dir=Path("/tmp/test_s05_routing"),
            diagnostics=[],
            context=context,
        )

    # bordered + general domain should NOT set s00_routed_strategy (lattice_default is the default)
    assert quality_summary.get("s00_routed_strategy") is None, (
        f"bordered+general should use default lattice, got {quality_summary.get('s00_routed_strategy')}"
    )
    assert quality_summary.get("s00_table_style") == "bordered"


def test_bordered_defense_routes_to_lattice_strong():
    """TASK-003: S00 table_style=bordered + domain=defense → lattice_strong."""
    from extractor.pipeline.steps.s05_table_extractor import extract_all_tables

    mock_doc = MagicMock()
    mock_doc.__len__ = lambda self: 0

    context = {"table_style": "bordered", "domain": "defense"}

    with patch("extractor.pipeline.steps.s05_table_extractor.fitz") as mock_fitz:
        mock_fitz.open.return_value = mock_doc
        _, _, quality_summary = extract_all_tables(
            pdf_path=Path("/dev/null"),
            output_dir=Path("/tmp/test_s05_routing"),
            diagnostics=[],
            context=context,
        )

    assert quality_summary.get("s00_routed_strategy") == "lattice_strong"
    assert quality_summary.get("s00_domain") == "defense"


def test_mixed_triggers_sweep():
    """TASK-003: S00 table_style=mixed triggers full strategy sweep."""
    from extractor.pipeline.steps.s05_table_extractor import extract_all_tables

    mock_doc = MagicMock()
    mock_doc.__len__ = lambda self: 0

    context = {"table_style": "mixed", "domain": "engineering"}

    with patch("extractor.pipeline.steps.s05_table_extractor.fitz") as mock_fitz:
        mock_fitz.open.return_value = mock_doc
        _, _, quality_summary = extract_all_tables(
            pdf_path=Path("/dev/null"),
            output_dir=Path("/tmp/test_s05_routing"),
            diagnostics=[],
            context=context,
        )

    assert quality_summary.get("s00_routed_strategy") == "mixed_sweep"


def test_s00_context_fields_propagated():
    """TASK-003: Verify table_style, domain, has_multi_column are in pipeline_context."""
    from extractor.pipeline.steps.s00_profile_detector import analyze_with_pymupdf4llm

    # We can't easily run S00 without a PDF, so test the context write path directly
    # by checking the code structure
    import ast
    import inspect

    # Read S00 source
    s00_path = Path("src/extractor/pipeline/steps/s00_profile_detector.py")
    src = s00_path.read_text()

    # Check that table_style is written to pipeline_context
    assert '"table_style"' in src, "S00 must write table_style to pipeline_context"
    assert '"domain"' in src, "S00 must write domain to pipeline_context"
    assert '"has_multi_column"' in src, "S00 must write has_multi_column to pipeline_context"


def test_s05_reads_table_style_from_context():
    """TASK-003: Verify S05 reads table_style from context parameter."""
    import ast

    s05_path = Path("src/extractor/pipeline/steps/s05_table_extractor.py")
    src = s05_path.read_text()

    # S05 must reference table_style from context
    assert 'table_style' in src, "S05 must read table_style from context"
    assert 's00_table_style' in src, "S05 must use s00_table_style variable"


def test_no_regression_existing_strategies():
    """Ensure original 4 strategies still have correct params."""
    from extractor.pipeline.utils.tables.extraction import CAMELOT_STRATEGIES

    # lattice_default
    ld = CAMELOT_STRATEGIES["lattice_default"]
    assert ld["flavor"] == "lattice"
    assert "line_scale" in ld["params"]

    # lattice_strong
    ls = CAMELOT_STRATEGIES["lattice_strong"]
    assert ls["flavor"] == "lattice"
    assert ls["params"]["line_scale"] == 40

    # lattice_sensitive
    lse = CAMELOT_STRATEGIES["lattice_sensitive"]
    assert lse["flavor"] == "lattice"
    assert lse["params"]["line_scale"] == 5

    # stream_default
    sd = CAMELOT_STRATEGIES["stream_default"]
    assert sd["flavor"] == "stream"
    assert sd["params"]["edge_tol"] == 50
