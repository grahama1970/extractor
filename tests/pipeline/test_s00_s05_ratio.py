"""Tests for S00 vs S05 table estimation comparison.

These tests verify that _compute_s00_s05_ratio() correctly:
1. Labels ratios as GOOD, ACCEPTABLE, S00_UNDERESTIMATE, S00_OVERESTIMATE
2. Handles edge cases (both 0, missing files)
3. Correctly computes ratios
"""

import json
import pytest
from pathlib import Path

# Import the function under test
import sys

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))
from debug_pdf_local import _compute_s00_s05_ratio


@pytest.fixture
def temp_pipeline_dir(tmp_path):
    """Create a temporary pipeline directory structure."""
    profile_dir = tmp_path / "00_profile_detector"
    profile_dir.mkdir()
    tables_dir = tmp_path / "05_table_extractor" / "json_output"
    tables_dir.mkdir(parents=True)
    return tmp_path


def write_profile(pipeline_dir: Path, estimated_table_count: int, drawing_pages: int = 0, max_per_page: int = 0):
    """Write a mock S00 profile."""
    profile = {
        "elements": {
            "estimated_table_count": estimated_table_count,
            "table_pages_drawing": drawing_pages,
            "max_tables_per_page": max_per_page,
        }
    }
    profile_path = pipeline_dir / "00_profile_detector" / "profile.json"
    profile_path.write_text(json.dumps(profile))


def write_tables(pipeline_dir: Path, table_count: int):
    """Write a mock S05 tables file."""
    tables = [{"id": f"table_{i}"} for i in range(table_count)]
    tables_path = pipeline_dir / "05_table_extractor" / "json_output" / "05_tables.json"
    tables_path.write_text(json.dumps(tables))


class TestRatioLabels:
    """Test ratio -> label mapping."""

    def test_good_ratio_exact_match(self, temp_pipeline_dir):
        """Ratio of 1.0x should be GOOD."""
        write_profile(temp_pipeline_dir, 10)
        write_tables(temp_pipeline_dir, 10)
        result = _compute_s00_s05_ratio(temp_pipeline_dir)
        assert result["available"] is True
        assert result["label"] == "GOOD"
        assert result["ratio"] == 1.0

    def test_good_ratio_within_2x_over(self, temp_pipeline_dir):
        """Ratio of 1.5x should be GOOD."""
        write_profile(temp_pipeline_dir, 10)
        write_tables(temp_pipeline_dir, 15)
        result = _compute_s00_s05_ratio(temp_pipeline_dir)
        assert result["label"] == "GOOD"
        assert 0.5 <= result["ratio"] <= 2.0

    def test_good_ratio_within_2x_under(self, temp_pipeline_dir):
        """Ratio of 0.6x should be GOOD."""
        write_profile(temp_pipeline_dir, 10)
        write_tables(temp_pipeline_dir, 6)
        result = _compute_s00_s05_ratio(temp_pipeline_dir)
        assert result["label"] == "GOOD"

    def test_acceptable_ratio_high(self, temp_pipeline_dir):
        """Ratio of 2.5x should be ACCEPTABLE."""
        write_profile(temp_pipeline_dir, 10)
        write_tables(temp_pipeline_dir, 25)
        result = _compute_s00_s05_ratio(temp_pipeline_dir)
        assert result["label"] == "ACCEPTABLE"
        assert 2.0 < result["ratio"] <= 3.0

    def test_acceptable_ratio_low(self, temp_pipeline_dir):
        """Ratio of 0.4x should be ACCEPTABLE."""
        write_profile(temp_pipeline_dir, 10)
        write_tables(temp_pipeline_dir, 4)
        result = _compute_s00_s05_ratio(temp_pipeline_dir)
        assert result["label"] == "ACCEPTABLE"
        assert 0.3 <= result["ratio"] < 0.5

    def test_underestimate_severe(self, temp_pipeline_dir):
        """Ratio > 3x means S00 significantly underestimated."""
        write_profile(temp_pipeline_dir, 5)
        write_tables(temp_pipeline_dir, 20)
        result = _compute_s00_s05_ratio(temp_pipeline_dir)
        assert result["label"] == "S00_UNDERESTIMATE"
        assert result["ratio"] > 3.0

    def test_overestimate_severe(self, temp_pipeline_dir):
        """Ratio < 0.3x means S00 significantly overestimated."""
        write_profile(temp_pipeline_dir, 20)
        write_tables(temp_pipeline_dir, 5)
        result = _compute_s00_s05_ratio(temp_pipeline_dir)
        assert result["label"] == "S00_OVERESTIMATE"
        assert result["ratio"] < 0.3


class TestEdgeCases:
    """Test edge cases."""

    def test_both_zero(self, temp_pipeline_dir):
        """Both S00 and S05 report 0 tables should be GOOD."""
        write_profile(temp_pipeline_dir, 0)
        write_tables(temp_pipeline_dir, 0)
        result = _compute_s00_s05_ratio(temp_pipeline_dir)
        assert result["available"] is True
        assert result["label"] == "GOOD"
        assert result["ratio"] == 1.0

    def test_s00_zero_s05_nonzero(self, temp_pipeline_dir):
        """S00 estimated 0 but S05 found tables = underestimate."""
        write_profile(temp_pipeline_dir, 0)
        write_tables(temp_pipeline_dir, 10)
        result = _compute_s00_s05_ratio(temp_pipeline_dir)
        assert result["label"] == "S00_UNDERESTIMATE"
        assert result["ratio"] == float("inf")

    def test_s00_nonzero_s05_zero(self, temp_pipeline_dir):
        """S00 estimated tables but S05 found 0 = overestimate."""
        write_profile(temp_pipeline_dir, 10)
        write_tables(temp_pipeline_dir, 0)
        result = _compute_s00_s05_ratio(temp_pipeline_dir)
        assert result["label"] == "S00_OVERESTIMATE"
        assert result["ratio"] == 0.0


class TestMissingFiles:
    """Test behavior when files are missing."""

    def test_missing_profile(self, tmp_path):
        """Missing S00 profile should return available=False."""
        result = _compute_s00_s05_ratio(tmp_path)
        assert result["available"] is False
        assert "profile not found" in result["analysis"].lower()

    def test_missing_tables(self, temp_pipeline_dir):
        """Missing S05 tables file should return available=False."""
        write_profile(temp_pipeline_dir, 10)
        # Don't write tables
        result = _compute_s00_s05_ratio(temp_pipeline_dir)
        assert result["available"] is False
        assert "tables not found" in result["analysis"].lower()

    def test_manifest_fallback(self, temp_pipeline_dir):
        """Should use manifest.json as fallback for table count."""
        write_profile(temp_pipeline_dir, 10)
        # Delete the tables.json but add manifest
        manifest = {"counts": {"tables05": 12}}
        (temp_pipeline_dir / "manifest.json").write_text(json.dumps(manifest))
        # Remove the json_output dir
        import shutil
        shutil.rmtree(temp_pipeline_dir / "05_table_extractor")

        result = _compute_s00_s05_ratio(temp_pipeline_dir)
        assert result["available"] is True
        assert result["s05_actual"] == 12


class TestRealWorldScenarios:
    """Test scenarios based on real pipeline runs."""

    def test_arxiv_typical(self, temp_pipeline_dir):
        """Typical arxiv paper: estimated 16, actual 20."""
        write_profile(temp_pipeline_dir, 16, drawing_pages=4, max_per_page=7)
        write_tables(temp_pipeline_dir, 20)
        result = _compute_s00_s05_ratio(temp_pipeline_dir)
        assert result["label"] == "GOOD"
        assert 1.0 <= result["ratio"] <= 1.5
        assert result["s00_drawing_pages"] == 4
        assert result["s00_max_per_page"] == 7

    def test_flowchart_heavy_pdf(self, temp_pipeline_dir):
        """PDF with flowcharts: S00 overestimates significantly."""
        write_profile(temp_pipeline_dir, 30, drawing_pages=10)
        write_tables(temp_pipeline_dir, 5)
        result = _compute_s00_s05_ratio(temp_pipeline_dir)
        assert result["label"] in ["S00_OVERESTIMATE", "ACCEPTABLE"]

    def test_dense_tables_pdf(self, temp_pipeline_dir):
        """PDF with many small tables: S00 might underestimate."""
        write_profile(temp_pipeline_dir, 10, max_per_page=3)
        write_tables(temp_pipeline_dir, 35)
        result = _compute_s00_s05_ratio(temp_pipeline_dir)
        assert result["label"] == "S00_UNDERESTIMATE"
