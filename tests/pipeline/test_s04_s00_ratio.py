"""Tests for S04/S00 quality ratio computation."""

import json
from pathlib import Path

from extractor.pipeline.steps.s04_section_builder import _compute_s00_s04_ratio


class TestS04S00Ratio:
    def _write_profile(self, tmp_path: Path, estimated: int = 50,
                       regex: int = 30, font: int = 50) -> Path:
        """Write a mock S00 profile.json under the expected directory structure."""
        profile_dir = tmp_path / "00_profile_detector"
        profile_dir.mkdir(parents=True, exist_ok=True)
        profile = {
            "hierarchy": {
                "estimated_sections": estimated,
                "estimated_sections_regex": regex,
                "estimated_sections_font": font,
            }
        }
        profile_path = profile_dir / "profile.json"
        profile_path.write_text(json.dumps(profile))

        # S04 output_dir is a sibling: tmp_path / "04_section_builder"
        s04_dir = tmp_path / "04_section_builder"
        s04_dir.mkdir(parents=True, exist_ok=True)
        return s04_dir

    def test_good_ratio(self, tmp_path):
        """Ratio 0.7-1.5x should be labeled GOOD."""
        s04_dir = self._write_profile(tmp_path, estimated=100)
        result = _compute_s00_s04_ratio(s04_dir, s04_section_count=100)

        assert result["available"] is True
        assert result["ratio"] == 1.0
        assert result["label"] == "GOOD"

    def test_acceptable_ratio(self, tmp_path):
        """Ratio 1.5-2.0x should be labeled ACCEPTABLE."""
        s04_dir = self._write_profile(tmp_path, estimated=60)
        result = _compute_s00_s04_ratio(s04_dir, s04_section_count=100)

        assert result["available"] is True
        assert 1.5 <= result["ratio"] <= 2.0
        assert result["label"] == "ACCEPTABLE"

    def test_underestimate(self, tmp_path):
        """Ratio >2x should be labeled S00_UNDERESTIMATE."""
        s04_dir = self._write_profile(tmp_path, estimated=20)
        result = _compute_s00_s04_ratio(s04_dir, s04_section_count=100)

        assert result["ratio"] == 5.0
        assert result["label"] == "S00_UNDERESTIMATE"

    def test_overestimate(self, tmp_path):
        """Ratio <0.5x should be labeled S00_OVERESTIMATE."""
        s04_dir = self._write_profile(tmp_path, estimated=200)
        result = _compute_s00_s04_ratio(s04_dir, s04_section_count=50)

        assert result["ratio"] == 0.25
        assert result["label"] == "S00_OVERESTIMATE"

    def test_missing_profile(self, tmp_path):
        """Missing S00 profile should return available=False."""
        s04_dir = tmp_path / "04_section_builder"
        s04_dir.mkdir(parents=True, exist_ok=True)

        result = _compute_s00_s04_ratio(s04_dir, s04_section_count=100)
        assert result["available"] is False

    def test_zero_estimate(self, tmp_path):
        """Zero S00 estimate should return INSUFFICIENT_DATA."""
        s04_dir = self._write_profile(tmp_path, estimated=0)
        result = _compute_s00_s04_ratio(s04_dir, s04_section_count=100)

        assert result["label"] == "INSUFFICIENT_DATA"

    def test_includes_regex_and_font_breakdown(self, tmp_path):
        """Result should include S00 regex and font sub-estimates."""
        s04_dir = self._write_profile(tmp_path, estimated=80, regex=30, font=80)
        result = _compute_s00_s04_ratio(s04_dir, s04_section_count=100)

        assert result["s00_regex"] == 30
        assert result["s00_font"] == 80
