"""Tests for calibration flight check gate.

Task 11: Create flight check gate.
"""

from unittest.mock import MagicMock, patch

from tools.tasks_loop.gates.gate_calibration import (
    run_flight_check,
    format_flight_check,
    FlightCheckResult,
)


class TestFlightCheckResult:
    """Test FlightCheckResult dataclass."""

    def test_result_has_all_fields(self):
        """Test result has required fields."""
        result = FlightCheckResult(
            passed=True,
            checks={"min_examples": True},
            stats={"reviewed": 25},
            missing=[],
            message="All checks passed",
        )

        assert result.passed is True
        assert "min_examples" in result.checks
        assert result.stats["reviewed"] == 25
        assert result.missing == []
        assert "passed" in result.message

    def test_failed_result(self):
        """Test failed result structure."""
        result = FlightCheckResult(
            passed=False,
            checks={"min_examples": False, "accuracy_threshold": True},
            stats={"reviewed": 15, "accuracy": 95.0},
            missing=["min_examples"],
            message="Flight check failed: min_examples",
        )

        assert result.passed is False
        assert result.checks["min_examples"] is False
        assert result.checks["accuracy_threshold"] is True
        assert "min_examples" in result.missing


class TestRunFlightCheck:
    """Test run_flight_check function."""

    @patch("extractor.pipeline.calibration.CalibrationSchema")
    @patch("extractor.pipeline.calibration.FeedbackHandler")
    @patch("extractor.pipeline.calibration.PatternLearner")
    def test_session_not_found(self, mock_learner, mock_handler, mock_schema):
        """Test returns failure when session not found."""
        mock_schema_instance = MagicMock()
        mock_schema_instance.get_session.return_value = None
        mock_schema.return_value = mock_schema_instance

        result = run_flight_check("nonexistent_session")

        assert result.passed is False
        assert "session_not_found" in result.missing
        assert "not found" in result.message

    @patch("extractor.pipeline.calibration.CalibrationSchema")
    @patch("extractor.pipeline.calibration.FeedbackHandler")
    @patch("extractor.pipeline.calibration.PatternLearner")
    def test_minimum_examples_check_fails(self, mock_learner, mock_handler, mock_schema):
        """Test gate fails if < 20 examples reviewed."""
        # Setup mocks
        mock_schema_instance = MagicMock()
        mock_schema_instance.get_session.return_value = {"preset_id": "test"}
        mock_schema.return_value = mock_schema_instance

        mock_handler_instance = MagicMock()
        mock_handler_instance.get_session_stats.return_value = {
            "reviewed": 15,  # Below threshold
            "accuracy": 95.0,
            "by_type": {
                "header": {"reviewed": 5},
                "table": {"reviewed": 5},
                "figure": {"reviewed": 5},
            },
        }
        mock_handler.return_value = mock_handler_instance

        mock_learner_instance = MagicMock()
        mock_learner_instance.get_active_patterns.return_value = [{"type": "header"}]
        mock_learner.return_value = mock_learner_instance

        result = run_flight_check("test_session")

        assert result.passed is False
        assert result.checks["min_examples"] is False
        assert "min_examples" in result.missing

    @patch("extractor.pipeline.calibration.CalibrationSchema")
    @patch("extractor.pipeline.calibration.FeedbackHandler")
    @patch("extractor.pipeline.calibration.PatternLearner")
    def test_accuracy_threshold_fails(self, mock_learner, mock_handler, mock_schema):
        """Test gate fails if accuracy < 90%."""
        mock_schema_instance = MagicMock()
        mock_schema_instance.get_session.return_value = {"preset_id": "test"}
        mock_schema.return_value = mock_schema_instance

        mock_handler_instance = MagicMock()
        mock_handler_instance.get_session_stats.return_value = {
            "reviewed": 25,
            "accuracy": 85.0,  # Below 90% threshold
            "by_type": {
                "header": {"reviewed": 10},
                "table": {"reviewed": 10},
                "figure": {"reviewed": 5},
            },
        }
        mock_handler.return_value = mock_handler_instance

        mock_learner_instance = MagicMock()
        mock_learner_instance.get_active_patterns.return_value = [{"type": "header"}]
        mock_learner.return_value = mock_learner_instance

        result = run_flight_check("test_session")

        assert result.passed is False
        assert result.checks["accuracy_threshold"] is False
        assert "accuracy_threshold" in result.missing

    @patch("extractor.pipeline.calibration.CalibrationSchema")
    @patch("extractor.pipeline.calibration.FeedbackHandler")
    @patch("extractor.pipeline.calibration.PatternLearner")
    def test_element_type_coverage_fails(self, mock_learner, mock_handler, mock_schema):
        """Test gate fails if any element type has < 3 examples."""
        mock_schema_instance = MagicMock()
        mock_schema_instance.get_session.return_value = {"preset_id": "test"}
        mock_schema.return_value = mock_schema_instance

        mock_handler_instance = MagicMock()
        mock_handler_instance.get_session_stats.return_value = {
            "reviewed": 25,
            "accuracy": 95.0,
            "by_type": {
                "header": {"reviewed": 10},
                "table": {"reviewed": 2},  # Below 3 threshold
                "figure": {"reviewed": 13},
            },
        }
        mock_handler.return_value = mock_handler_instance

        mock_learner_instance = MagicMock()
        mock_learner_instance.get_active_patterns.return_value = [{"type": "header"}]
        mock_learner.return_value = mock_learner_instance

        result = run_flight_check("test_session")

        assert result.passed is False
        assert result.checks["has_tables"] is False
        assert "has_tables" in result.missing

    @patch("extractor.pipeline.calibration.CalibrationSchema")
    @patch("extractor.pipeline.calibration.FeedbackHandler")
    @patch("extractor.pipeline.calibration.PatternLearner")
    def test_missing_figures_fails(self, mock_learner, mock_handler, mock_schema):
        """Test gate fails if figures have < 3 examples."""
        mock_schema_instance = MagicMock()
        mock_schema_instance.get_session.return_value = {"preset_id": "test"}
        mock_schema.return_value = mock_schema_instance

        mock_handler_instance = MagicMock()
        mock_handler_instance.get_session_stats.return_value = {
            "reviewed": 25,
            "accuracy": 95.0,
            "by_type": {
                "header": {"reviewed": 10},
                "table": {"reviewed": 10},
                "figure": {"reviewed": 1},  # Below 3 threshold
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

    @patch("extractor.pipeline.calibration.CalibrationSchema")
    @patch("extractor.pipeline.calibration.FeedbackHandler")
    @patch("extractor.pipeline.calibration.PatternLearner")
    def test_pattern_check_optional(self, mock_learner, mock_handler, mock_schema):
        """Test patterns are tracked but not required for pass."""
        mock_schema_instance = MagicMock()
        mock_schema_instance.get_session.return_value = {"preset_id": "test"}
        mock_schema.return_value = mock_schema_instance

        mock_handler_instance = MagicMock()
        mock_handler_instance.get_session_stats.return_value = {
            "reviewed": 25,
            "accuracy": 95.0,
            "by_type": {
                "header": {"reviewed": 10},
                "table": {"reviewed": 10},
                "figure": {"reviewed": 5},
            },
        }
        mock_handler.return_value = mock_handler_instance

        mock_learner_instance = MagicMock()
        mock_learner_instance.get_active_patterns.return_value = []  # No patterns
        mock_learner.return_value = mock_learner_instance

        result = run_flight_check("test_session")

        # Should still pass - patterns are optional
        assert result.passed is True
        assert result.checks["has_patterns"] is False
        assert "has_patterns" not in result.missing  # Not in missing because optional

    @patch("extractor.pipeline.calibration.CalibrationSchema")
    @patch("extractor.pipeline.calibration.FeedbackHandler")
    @patch("extractor.pipeline.calibration.PatternLearner")
    def test_pass_with_good_session(self, mock_learner, mock_handler, mock_schema):
        """Test gate passes with well-calibrated session."""
        mock_schema_instance = MagicMock()
        mock_schema_instance.get_session.return_value = {"preset_id": "test"}
        mock_schema.return_value = mock_schema_instance

        mock_handler_instance = MagicMock()
        mock_handler_instance.get_session_stats.return_value = {
            "reviewed": 30,
            "accuracy": 95.0,
            "by_type": {
                "header": {"reviewed": 12},
                "table": {"reviewed": 10},
                "figure": {"reviewed": 8},
            },
        }
        mock_handler.return_value = mock_handler_instance

        mock_learner_instance = MagicMock()
        mock_learner_instance.get_active_patterns.return_value = [
            {"type": "header"},
            {"type": "table"},
        ]
        mock_learner.return_value = mock_learner_instance

        result = run_flight_check("test_session")

        assert result.passed is True
        assert all(
            result.checks[c]
            for c in [
                "min_examples",
                "accuracy_threshold",
                "has_headers",
                "has_tables",
                "has_figures",
            ]
        )
        assert result.missing == []
        assert "passed" in result.message.lower()

    @patch("extractor.pipeline.calibration.CalibrationSchema")
    @patch("extractor.pipeline.calibration.FeedbackHandler")
    @patch("extractor.pipeline.calibration.PatternLearner")
    def test_multiple_failures(self, mock_learner, mock_handler, mock_schema):
        """Test multiple failures are all reported."""
        mock_schema_instance = MagicMock()
        mock_schema_instance.get_session.return_value = {"preset_id": "test"}
        mock_schema.return_value = mock_schema_instance

        mock_handler_instance = MagicMock()
        mock_handler_instance.get_session_stats.return_value = {
            "reviewed": 10,  # Fail
            "accuracy": 80.0,  # Fail
            "by_type": {
                "header": {"reviewed": 5},
                "table": {"reviewed": 3},
                "figure": {"reviewed": 2},  # Fail
            },
        }
        mock_handler.return_value = mock_handler_instance

        mock_learner_instance = MagicMock()
        mock_learner_instance.get_active_patterns.return_value = []
        mock_learner.return_value = mock_learner_instance

        result = run_flight_check("test_session")

        assert result.passed is False
        assert "min_examples" in result.missing
        assert "accuracy_threshold" in result.missing
        assert "has_figures" in result.missing


class TestFormatFlightCheck:
    """Test format_flight_check function."""

    def test_format_passing_result(self):
        """Test formatting a passing result."""
        result = FlightCheckResult(
            passed=True,
            checks={
                "min_examples": True,
                "accuracy_threshold": True,
                "has_headers": True,
                "has_tables": True,
                "has_figures": True,
                "has_patterns": True,
            },
            stats={"reviewed": 30, "accuracy": 95.0},
            missing=[],
            message="All flight checks passed!",
        )

        formatted = format_flight_check(result)

        assert "Flight Check Results:" in formatted
        assert "PASS" in formatted
        assert "✔" in formatted
        # Should show all checks with checkmarks
        assert formatted.count("✔") == 6

    def test_format_failing_result(self):
        """Test formatting a failing result."""
        result = FlightCheckResult(
            passed=False,
            checks={
                "min_examples": False,
                "accuracy_threshold": True,
                "has_headers": True,
                "has_tables": False,
                "has_figures": True,
                "has_patterns": False,
            },
            stats={"reviewed": 15, "accuracy": 92.0},
            missing=["min_examples", "has_tables"],
            message="Flight check failed: min_examples, has_tables",
        )

        formatted = format_flight_check(result)

        assert "Flight Check Results:" in formatted
        assert "FAIL" in formatted
        assert "✗" in formatted
        assert "Missing:" in formatted
        assert "min_examples" in formatted
        assert "has_tables" in formatted

    def test_format_shows_all_check_names(self):
        """Test all check names are displayed properly."""
        result = FlightCheckResult(
            passed=True,
            checks={
                "min_examples": True,
                "accuracy_threshold": True,
                "has_headers": True,
            },
            stats={},
            missing=[],
            message="Pass",
        )

        formatted = format_flight_check(result)

        assert "Min Examples" in formatted
        assert "Accuracy Threshold" in formatted
        assert "Has Headers" in formatted
