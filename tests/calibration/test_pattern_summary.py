"""Tests for pattern summary query.

Task 9: Implement 'what have you learned?' query.
"""

import pytest

from extractor.pipeline.calibration import (
    CalibrationSchema,
    CalibrationSession,
    SessionStatus,
    PatternLearner,
)


@pytest.fixture
def session_with_patterns():
    """Create a session with patterns and examples."""
    schema = CalibrationSchema()
    session_key = "test-pattern-summary-session"
    preset_id = "test-summary-preset"

    # Clean up
    try:
        schema.sessions.delete(session_key)
    except Exception:
        pass

    # Create session
    session = CalibrationSession(
        key=session_key,
        preset_id=preset_id,
        client="test",
        pdf_path="/tmp/test.pdf",
        page_count=10,
        status=SessionStatus.IN_PROGRESS,
        owner="test",
    )
    schema.create_session(session.to_arango())

    # Add examples
    for i in range(5):
        schema.examples.insert(
            {
                "_key": f"sum_header_{i}",
                "session_key": session_key,
                "element_type": "header",
                "human_verdict": "correct" if i < 4 else "wrong_type",
            }
        )

    for i in range(3):
        schema.examples.insert(
            {
                "_key": f"sum_table_{i}",
                "session_key": session_key,
                "element_type": "table",
                "human_verdict": "correct",
            }
        )

    # Add patterns
    schema.patterns.insert(
        {
            "_key": f"{preset_id}_header_pattern",
            "preset_id": preset_id,
            "element_type": "header",
            "stage1_regex": r"^\d+\.\d+",
            "stage2_python": "def v():\n    if font_info.get('size', 0) >= 14:\n        pass",
            "active": True,
        }
    )

    schema.patterns.insert(
        {
            "_key": f"{preset_id}_table_pattern",
            "preset_id": preset_id,
            "element_type": "table",
            "stage2_python": "params = {'flavor': 'lattice'}",
            "active": True,
        }
    )

    yield schema, session_key, preset_id

    # Cleanup
    try:
        schema.sessions.delete(session_key)
        for i in range(5):
            schema.examples.delete(f"sum_header_{i}")
        for i in range(3):
            schema.examples.delete(f"sum_table_{i}")
        schema.patterns.delete(f"{preset_id}_header_pattern")
        schema.patterns.delete(f"{preset_id}_table_pattern")
    except Exception:
        pass


class TestPatternSummary:
    """Test pattern summary generation."""

    def test_summary_includes_pattern_count(self, session_with_patterns):
        """Test summary shows pattern count."""
        schema, session_key, preset_id = session_with_patterns
        learner = PatternLearner(schema)

        summary = learner.get_pattern_summary(session_key)

        assert "Header" in summary
        assert "Table" in summary

    def test_summary_includes_accuracy(self, session_with_patterns):
        """Test summary shows accuracy."""
        schema, session_key, preset_id = session_with_patterns
        learner = PatternLearner(schema)

        summary = learner.get_pattern_summary(session_key)

        # Headers: 4/5 correct = 80%
        assert "80%" in summary or "5 examples" in summary

    def test_summary_includes_pattern_details(self, session_with_patterns):
        """Test summary shows pattern details."""
        schema, session_key, preset_id = session_with_patterns
        learner = PatternLearner(schema)

        summary = learner.get_pattern_summary(session_key)

        # Should include regex pattern
        assert "Pattern" in summary or "`" in summary
        # Should include font size
        assert "14pt" in summary or "Font size" in summary

    def test_summary_no_patterns(self):
        """Test summary when no patterns exist."""
        schema = CalibrationSchema()
        session_key = "test-no-patterns"

        # Create empty session
        try:
            schema.sessions.delete(session_key)
        except Exception:
            pass

        session = CalibrationSession(
            key=session_key,
            preset_id="empty-preset",
            client="test",
            pdf_path="/tmp/test.pdf",
            page_count=1,
            status=SessionStatus.IN_PROGRESS,
            owner="test",
        )
        schema.create_session(session.to_arango())

        learner = PatternLearner(schema)
        summary = learner.get_pattern_summary(session_key)

        assert "No patterns" in summary or "Keep reviewing" in summary

        # Cleanup
        try:
            schema.sessions.delete(session_key)
        except Exception:
            pass
