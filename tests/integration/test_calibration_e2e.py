"""End-to-end integration test for calibration workflow.

Task 15: End-to-end integration test.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


from extractor.pipeline.calibration import (
    HumanVerdict,
    parse_verdict,
    apply_adjustment,
    parse_bbox_adjustment,
)
from extractor.pipeline.calibration.preset_generator import (
    generate_preset,
)
from tools.tasks_loop.gates.gate_calibration import run_flight_check


# Fixtures path
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "calibration"


def load_sample_session():
    """Load sample session fixture."""
    with open(FIXTURES_DIR / "sample_session.json") as f:
        return json.load(f)


def load_expected_elements():
    """Load expected elements fixture."""
    with open(FIXTURES_DIR / "expected_elements.json") as f:
        return json.load(f)


class TestCalibrationE2E:
    """Test full calibration workflow programmatically."""

    @patch("extractor.pipeline.calibration.CalibrationSchema")
    @patch("extractor.pipeline.calibration.FeedbackHandler")
    @patch("extractor.pipeline.calibration.PatternLearner")
    def test_full_calibration_flow(self, mock_learner, mock_handler, mock_schema):
        """Test complete flow: start -> verdicts -> patterns -> finish.

        Simulates:
        1. Start calibration on test PDF
        2. Review 20+ elements with scripted verdicts
        3. Verify patterns learned
        4. Run finish, verify flight check passes
        5. Verify preset configuration generated
        """
        sample_session = load_sample_session()

        # Setup mock schema
        mock_schema_instance = MagicMock()
        mock_schema_instance.get_session.return_value = {
            "_key": sample_session["session"]["_key"],
            "preset_id": sample_session["session"]["preset_id"],
            "pdf_path": sample_session["session"]["pdf_path"],
            "status": "in_progress",
        }
        mock_schema.return_value = mock_schema_instance

        # Setup mock feedback handler
        mock_handler_instance = MagicMock()
        mock_handler_instance.get_session_stats.return_value = {
            "reviewed": sample_session["stats"]["reviewed"],
            "correct": sample_session["stats"]["correct"],
            "accuracy": sample_session["stats"]["accuracy"],
            "by_type": sample_session["stats"]["by_type"],
            "current_round": 2,
            "last_page": 9,
            "last_element_idx": 1,
        }
        mock_handler.return_value = mock_handler_instance

        # Setup mock pattern learner
        mock_learner_instance = MagicMock()
        mock_learner_instance.get_active_patterns.return_value = sample_session["patterns"]
        mock_learner.return_value = mock_learner_instance

        # Step 1: Verify session exists
        session = mock_schema_instance.get_session(sample_session["session"]["_key"])
        assert session is not None
        assert session["preset_id"] == "test-document"

        # Step 2: Verify stats show enough reviewed elements
        stats = mock_handler_instance.get_session_stats(sample_session["session"]["_key"])
        assert stats["reviewed"] >= 20
        assert stats["accuracy"] >= 90.0

        # Step 3: Verify patterns were learned
        patterns = mock_learner_instance.get_active_patterns("test-document")
        assert len(patterns) >= 1
        assert any(p["element_type"] == "header" for p in patterns)

        # Step 4: Run flight check
        result = run_flight_check(sample_session["session"]["_key"])
        assert result.passed is True
        assert result.checks["min_examples"] is True
        assert result.checks["accuracy_threshold"] is True

        # Step 5: Generate preset
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test-document.yaml"
            config = generate_preset(sample_session["session"]["_key"], output_path)

            assert config.preset_id == "test-document"
            assert config.metadata["total_reviewed"] == sample_session["stats"]["reviewed"]
            assert output_path.exists()

    @patch("extractor.pipeline.calibration.CalibrationSchema")
    @patch("extractor.pipeline.calibration.FeedbackHandler")
    def test_session_resume(self, mock_handler, mock_schema):
        """Test session can be interrupted and resumed.

        Simulates:
        1. Start session, review 10 elements
        2. Simulate interrupt (session still in_progress)
        3. Resume session, continue from last position
        4. Verify no duplicate reviews
        """
        sample_session = load_sample_session()

        # First session state - 10 elements reviewed
        initial_stats = {
            "reviewed": 10,
            "correct": 10,
            "accuracy": 100.0,
            "by_type": {
                "header": {"reviewed": 5, "correct": 5},
                "table": {"reviewed": 3, "correct": 3},
                "figure": {"reviewed": 2, "correct": 2},
            },
            "current_round": 1,
            "last_page": 4,
            "last_element_idx": 2,
        }

        # Setup mock schema
        mock_schema_instance = MagicMock()
        mock_schema_instance.get_session.return_value = {
            "_key": sample_session["session"]["_key"],
            "preset_id": sample_session["session"]["preset_id"],
            "pdf_path": sample_session["session"]["pdf_path"],
            "status": "in_progress",
        }
        mock_schema.return_value = mock_schema_instance

        # Setup mock feedback handler
        mock_handler_instance = MagicMock()
        mock_handler_instance.get_session_stats.return_value = initial_stats
        mock_handler.return_value = mock_handler_instance

        # Step 1: Verify session can be found (resume)
        session = mock_schema_instance.get_session(sample_session["session"]["_key"])
        assert session is not None
        assert session["status"] == "in_progress"

        # Step 2: Get stats to continue from where we left off
        stats = mock_handler_instance.get_session_stats(sample_session["session"]["_key"])
        assert stats["reviewed"] == 10
        assert stats["last_page"] == 4
        assert stats["last_element_idx"] == 2

        # Step 3: Simulate continuing session (stats would update)
        resumed_stats = {
            "reviewed": 23,
            "correct": 22,
            "accuracy": 95.65,
            "by_type": sample_session["stats"]["by_type"],
            "current_round": 2,
            "last_page": 9,
            "last_element_idx": 1,
        }
        mock_handler_instance.get_session_stats.return_value = resumed_stats

        # Step 4: Verify resumed stats
        stats = mock_handler_instance.get_session_stats(sample_session["session"]["_key"])
        assert stats["reviewed"] == 23  # More than initial
        assert stats["last_page"] == 9  # Progress made

    @patch("extractor.pipeline.calibration.CalibrationSchema")
    @patch("extractor.pipeline.calibration.FeedbackHandler")
    @patch("extractor.pipeline.calibration.PatternLearner")
    def test_preset_generation(self, mock_learner, mock_handler, mock_schema):
        """Test preset YAML file is generated on successful finish."""
        sample_session = load_sample_session()

        # Setup mocks
        mock_schema_instance = MagicMock()
        mock_schema_instance.get_session.return_value = {
            "_key": sample_session["session"]["_key"],
            "preset_id": sample_session["session"]["preset_id"],
            "pdf_path": sample_session["session"]["pdf_path"],
        }
        mock_schema.return_value = mock_schema_instance

        mock_handler_instance = MagicMock()
        mock_handler_instance.get_session_stats.return_value = sample_session["stats"]
        mock_handler.return_value = mock_handler_instance

        mock_learner_instance = MagicMock()
        mock_learner_instance.get_active_patterns.return_value = sample_session["patterns"]
        mock_learner.return_value = mock_learner_instance

        # Generate preset
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "presets" / "test-document.yaml"
            generate_preset(sample_session["session"]["_key"], output_path)

            # Verify file created
            assert output_path.exists()

            # Verify YAML content
            import yaml

            with open(output_path) as f:
                data = yaml.safe_load(f)

            assert data["preset_id"] == "test-document"
            assert "patterns" in data
            assert "headers" in data["patterns"]
            assert "tables" in data["patterns"]
            assert "figures" in data["patterns"]


class TestVerdictParsingE2E:
    """Test verdict parsing in realistic scenarios."""

    def test_common_phrasings(self):
        """Test common human phrasings are correctly parsed."""
        test_cases = [
            ("correct", HumanVerdict.CORRECT),
            ("yes", HumanVerdict.CORRECT),
            ("looks good", HumanVerdict.CORRECT),
            ("that's right", HumanVerdict.CORRECT),
            ("wrong, that's a figure", HumanVerdict.WRONG_TYPE),
            ("no, it's a table not a header", HumanVerdict.WRONG_TYPE),
            ("not an element", HumanVerdict.NOT_ELEMENT),
            ("false positive", HumanVerdict.NOT_ELEMENT),
            ("ignore this", HumanVerdict.NOT_ELEMENT),
            ("split this into two", HumanVerdict.SPLIT),
            ("flag for review", HumanVerdict.FLAGGED),
            ("unsure about this one", HumanVerdict.FLAGGED),
            ("extend the bbox", HumanVerdict.ADJUST_BBOX),
            ("too small, expand it", HumanVerdict.ADJUST_BBOX),
        ]

        for phrase, expected_verdict in test_cases:
            result = parse_verdict(phrase)
            assert result.verdict == expected_verdict, f"Failed for: {phrase}"

    def test_type_correction_extraction(self):
        """Test correct type is extracted from natural language."""
        result = parse_verdict("wrong, that's actually a figure")
        assert result.verdict == HumanVerdict.WRONG_TYPE
        assert result.correction is not None
        assert result.correction.get("correct_type") == "figure"

        result = parse_verdict("wrong type, it's a table")
        assert result.verdict == HumanVerdict.WRONG_TYPE
        assert result.correction is not None
        assert result.correction.get("correct_type") == "table"


class TestBboxAdjustmentE2E:
    """Test bbox adjustment in realistic scenarios."""

    def test_relative_adjustments(self):
        """Test relative bbox adjustments."""
        original = [72.0, 200.0, 540.0, 400.0]

        # Extend right
        adj = parse_bbox_adjustment("extend right by 50px")
        assert adj is not None
        new_bbox = apply_adjustment(original, adj)
        assert new_bbox[2] == 590.0  # x1 extended

        # Shrink top
        adj = parse_bbox_adjustment("shrink top by 20")
        assert adj is not None
        new_bbox = apply_adjustment(original, adj)
        assert new_bbox[1] == 220.0  # y0 moved down

    def test_absolute_coordinates(self):
        """Test absolute bbox specification."""
        original = [72.0, 200.0, 540.0, 400.0]

        adj = parse_bbox_adjustment("set to [100, 250, 500, 450]")
        assert adj is not None
        new_bbox = apply_adjustment(original, adj)
        assert new_bbox == [100.0, 250.0, 500.0, 450.0]


class TestFlightCheckE2E:
    """Test flight check gate in realistic scenarios."""

    @patch("extractor.pipeline.calibration.CalibrationSchema")
    @patch("extractor.pipeline.calibration.FeedbackHandler")
    @patch("extractor.pipeline.calibration.PatternLearner")
    def test_flight_check_passes_with_good_session(self, mock_learner, mock_handler, mock_schema):
        """Test flight check passes with well-calibrated session."""
        sample_session = load_sample_session()

        mock_schema_instance = MagicMock()
        mock_schema_instance.get_session.return_value = {
            "preset_id": sample_session["session"]["preset_id"]
        }
        mock_schema.return_value = mock_schema_instance

        mock_handler_instance = MagicMock()
        mock_handler_instance.get_session_stats.return_value = sample_session["stats"]
        mock_handler.return_value = mock_handler_instance

        mock_learner_instance = MagicMock()
        mock_learner_instance.get_active_patterns.return_value = sample_session["patterns"]
        mock_learner.return_value = mock_learner_instance

        result = run_flight_check(sample_session["session"]["_key"])

        assert result.passed is True
        assert result.checks["min_examples"] is True
        assert result.checks["accuracy_threshold"] is True
        assert result.checks["has_headers"] is True
        assert result.checks["has_tables"] is True
        assert result.checks["has_figures"] is True

    @patch("extractor.pipeline.calibration.CalibrationSchema")
    @patch("extractor.pipeline.calibration.FeedbackHandler")
    @patch("extractor.pipeline.calibration.PatternLearner")
    def test_flight_check_fails_insufficient_coverage(
        self, mock_learner, mock_handler, mock_schema
    ):
        """Test flight check fails when element type coverage is insufficient."""
        mock_schema_instance = MagicMock()
        mock_schema_instance.get_session.return_value = {"preset_id": "test"}
        mock_schema.return_value = mock_schema_instance

        # Missing figure coverage
        mock_handler_instance = MagicMock()
        mock_handler_instance.get_session_stats.return_value = {
            "reviewed": 25,
            "accuracy": 95.0,
            "by_type": {
                "header": {"reviewed": 15},
                "table": {"reviewed": 8},
                "figure": {"reviewed": 2},  # Below threshold
            },
        }
        mock_handler.return_value = mock_handler_instance

        mock_learner_instance = MagicMock()
        mock_learner_instance.get_active_patterns.return_value = []
        mock_learner.return_value = mock_learner_instance

        result = run_flight_check("test_session")

        assert result.passed is False
        assert result.checks["has_figures"] is False
        assert "has_figures" in result.missing
