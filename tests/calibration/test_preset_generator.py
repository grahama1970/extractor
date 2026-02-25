"""Tests for preset configuration generator.

Task 13: Generate preset configuration file.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import yaml

from extractor.pipeline.calibration.preset_generator import (
    generate_preset,
    write_preset_yaml,
    format_preset_summary,
    PresetConfig,
    _build_header_patterns,
    _build_table_patterns,
    _build_figure_patterns,
)


class TestPresetConfig:
    """Test PresetConfig dataclass."""

    def test_config_has_all_fields(self):
        """Test PresetConfig has required fields."""
        config = PresetConfig(
            preset_id="test-preset",
            created="2026-01-20",
            calibrated_from="session_123",
            source_pdf="/path/to/doc.pdf",
            patterns={"headers": {}},
            thresholds={"header_confidence": 0.85},
            metadata={"total_reviewed": 30},
        )

        assert config.preset_id == "test-preset"
        assert config.created == "2026-01-20"
        assert config.calibrated_from == "session_123"
        assert config.source_pdf == "/path/to/doc.pdf"
        assert "headers" in config.patterns
        assert config.thresholds["header_confidence"] == 0.85
        assert config.metadata["total_reviewed"] == 30


class TestBuildPatterns:
    """Test pattern building helpers."""

    def test_build_header_patterns_with_regex(self):
        """Test header pattern building extracts regex."""
        patterns = [
            {
                "element_type": "header",
                "pattern_data": {
                    "regex": r"^\d+\.\d+\s+",
                    "font_size_min": 14,
                    "is_bold": True,
                },
            }
        ]

        result = _build_header_patterns(patterns, {})

        assert result["stage1_regex"] == r"^\d+\.\d+\s+"
        assert "font_size >= 14" in result["stage2_python"]
        assert "font_bold" in result["stage2_python"]

    def test_build_header_patterns_multiple_regex(self):
        """Test header patterns combine multiple regex."""
        patterns = [
            {"element_type": "header", "pattern_data": {"regex": r"^\d+\."}},
            {"element_type": "header", "pattern_data": {"regex": r"^Section"}},
        ]

        result = _build_header_patterns(patterns, {})

        assert r"^\d+\." in result["stage1_regex"]
        assert "^Section" in result["stage1_regex"]
        assert "|" in result["stage1_regex"]

    def test_build_table_patterns_with_methods(self):
        """Test table pattern building extracts detection methods."""
        patterns = [
            {
                "element_type": "table",
                "pattern_data": {
                    "has_grid_lines": True,
                    "has_caption": True,
                },
            }
        ]

        result = _build_table_patterns(patterns, {})

        assert "grid_lines" in result["detection"]
        assert "caption_above" in result["detection"]
        assert result["merge_threshold"] == 0.9

    def test_build_figure_patterns_with_caption(self):
        """Test figure pattern building extracts caption info."""
        patterns = [
            {
                "element_type": "figure",
                "pattern_data": {
                    "caption_regex": r"Fig\.\s+\d+",
                    "caption_position": "above",
                },
            }
        ]

        result = _build_figure_patterns(patterns, {})

        assert result["caption_pattern"] == r"Fig\.\s+\d+"
        assert result["caption_position"] == "above"

    def test_build_figure_patterns_defaults(self):
        """Test figure patterns have sensible defaults."""
        result = _build_figure_patterns([], {})

        assert result["caption_pattern"] == r"Figure\s+\d+\.?\d*"
        assert result["caption_position"] == "below"


class TestGeneratePreset:
    """Test generate_preset function."""

    @patch("extractor.pipeline.calibration.CalibrationSchema")
    @patch("extractor.pipeline.calibration.FeedbackHandler")
    @patch("extractor.pipeline.calibration.PatternLearner")
    def test_generate_preset_success(self, mock_learner, mock_handler, mock_schema):
        """Test successful preset generation."""
        # Setup mocks
        mock_schema_instance = MagicMock()
        mock_schema_instance.get_session.return_value = {
            "preset_id": "test-preset",
            "pdf_path": "/path/to/doc.pdf",
        }
        mock_schema.return_value = mock_schema_instance

        mock_handler_instance = MagicMock()
        mock_handler_instance.get_session_stats.return_value = {
            "reviewed": 30,
            "accuracy": 95.0,
            "by_type": {
                "header": {"reviewed": 12, "correct": 11},
                "table": {"reviewed": 10, "correct": 9},
                "figure": {"reviewed": 8, "correct": 8},
            },
        }
        mock_handler.return_value = mock_handler_instance

        mock_learner_instance = MagicMock()
        mock_learner_instance.get_active_patterns.return_value = [
            {"element_type": "header", "pattern_data": {"regex": r"^\d+\."}},
        ]
        mock_learner.return_value = mock_learner_instance

        config = generate_preset("test_session")

        assert config.preset_id == "test-preset"
        assert config.calibrated_from == "test_session"
        assert config.metadata["total_reviewed"] == 30
        assert config.metadata["accuracy"] == 95.0
        assert "headers" in config.patterns

    @patch("extractor.pipeline.calibration.CalibrationSchema")
    def test_generate_preset_session_not_found(self, mock_schema):
        """Test error when session not found."""
        mock_schema_instance = MagicMock()
        mock_schema_instance.get_session.return_value = None
        mock_schema.return_value = mock_schema_instance

        with pytest.raises(ValueError, match="not found"):
            generate_preset("nonexistent")


class TestWritePresetYaml:
    """Test write_preset_yaml function."""

    def test_write_creates_file(self):
        """Test YAML file is created."""
        config = PresetConfig(
            preset_id="test-preset",
            created="2026-01-20",
            calibrated_from="session_123",
            source_pdf="/path/to/doc.pdf",
            patterns={"headers": {"stage1_regex": r"^\d+\."}},
            thresholds={"header_confidence": 0.85},
            metadata={"total_reviewed": 30, "accuracy": 95.0},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "presets" / "test.yaml"
            write_preset_yaml(config, output_path)

            assert output_path.exists()

            # Verify YAML content
            with open(output_path) as f:
                content = f.read()

            assert "preset_id: test-preset" in content
            assert "# Generated from calibration session" in content

    def test_write_creates_parent_dirs(self):
        """Test parent directories are created."""
        config = PresetConfig(
            preset_id="test",
            created="2026-01-20",
            calibrated_from="session",
            source_pdf="doc.pdf",
            patterns={},
            thresholds={},
            metadata={},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "deep" / "nested" / "path" / "preset.yaml"
            write_preset_yaml(config, output_path)

            assert output_path.exists()

    def test_write_yaml_is_valid(self):
        """Test written YAML can be parsed."""
        config = PresetConfig(
            preset_id="test-preset",
            created="2026-01-20",
            calibrated_from="session_123",
            source_pdf="/path/to/doc.pdf",
            patterns={
                "headers": {"stage1_regex": r"^\d+\.\d+"},
                "tables": {"detection": ["grid_lines"]},
            },
            thresholds={"header_confidence": 0.85},
            metadata={"total_reviewed": 30},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.yaml"
            write_preset_yaml(config, output_path)

            # Parse and verify
            with open(output_path) as f:
                data = yaml.safe_load(f)

            assert data["preset_id"] == "test-preset"
            assert data["patterns"]["headers"]["stage1_regex"] == r"^\d+\.\d+"


class TestFormatPresetSummary:
    """Test format_preset_summary function."""

    def test_format_includes_key_stats(self):
        """Test summary includes key statistics."""
        config = PresetConfig(
            preset_id="boeing-spec",
            created="2026-01-20",
            calibrated_from="session_123",
            source_pdf="doc.pdf",
            patterns={},
            thresholds={},
            metadata={
                "total_reviewed": 45,
                "accuracy": 94.5,
                "patterns_learned": 3,
                "by_type": {
                    "header": {"reviewed": 20, "correct": 19},
                    "table": {"reviewed": 15, "correct": 14},
                    "figure": {"reviewed": 10, "correct": 10},
                },
            },
        )

        summary = format_preset_summary(config)

        assert "Calibration Complete!" in summary
        assert "45" in summary  # total_reviewed
        assert "94.5%" in summary  # accuracy
        assert "3" in summary  # patterns_learned
        assert "boeing-spec" in summary  # preset_id

    def test_format_includes_type_breakdown(self):
        """Test summary includes per-type breakdown."""
        config = PresetConfig(
            preset_id="test",
            created="2026-01-20",
            calibrated_from="session",
            source_pdf="doc.pdf",
            patterns={},
            thresholds={},
            metadata={
                "total_reviewed": 30,
                "accuracy": 90.0,
                "patterns_learned": 2,
                "by_type": {
                    "header": {"reviewed": 10, "correct": 9},
                },
            },
        )

        summary = format_preset_summary(config)

        assert "Header:" in summary
        assert "10 reviewed" in summary
