"""Tests for pattern proposal in calibration conversation.

Task 8: Integrate pattern proposal into conversation.
"""

import pytest

from extractor.pipeline.calibration import (
    CalibrationSchema,
    CalibrationSession,
    SessionStatus,
    PatternLearner,
    PatternProposal,
)


@pytest.fixture
def test_session():
    """Create a test calibration session."""
    schema = CalibrationSchema()
    session = CalibrationSession(
        key="test-pattern-proposal-session",
        preset_id="test-pattern-preset",
        client="test",
        pdf_path="/tmp/test.pdf",
        page_count=10,
        status=SessionStatus.IN_PROGRESS,
        owner="test",
    )

    # Clean up any existing session
    existing = schema.get_session("test-pattern-proposal-session")
    if existing:
        schema.sessions.delete("test-pattern-proposal-session")

    schema.create_session(session.to_arango())
    yield schema, "test-pattern-proposal-session"

    # Cleanup
    try:
        schema.sessions.delete("test-pattern-proposal-session")
        # Clean up examples
        examples = schema.list_examples(session_key="test-pattern-proposal-session")
        for ex in examples:
            schema.examples.delete(ex["_key"])
    except Exception:
        pass


class TestShouldProposePattern:
    """Test pattern proposal threshold checking."""

    def test_no_proposal_with_few_examples(self, test_session):
        """Test no proposal when under threshold."""
        schema, session_key = test_session
        learner = PatternLearner(schema)

        # Add 3 header examples (under threshold of 5)
        for i in range(3):
            schema.examples.insert(
                {
                    "_key": f"header_ex_{i}",
                    "session_key": session_key,
                    "element_type": "header",
                    "human_verdict": "correct",
                }
            )

        result = learner.should_propose_pattern(session_key, "header", threshold=5)
        assert result is False

    def test_proposal_when_threshold_met(self, test_session):
        """Test proposal when threshold is met."""
        schema, session_key = test_session
        learner = PatternLearner(schema)

        # Add 5 header examples (at threshold)
        for i in range(5):
            schema.examples.insert(
                {
                    "_key": f"header_thresh_{i}",
                    "session_key": session_key,
                    "element_type": "header",
                    "human_verdict": "correct",
                }
            )

        result = learner.should_propose_pattern(session_key, "header", threshold=5)
        assert result is True

    def test_no_proposal_if_pattern_exists(self, test_session):
        """Test no proposal if pattern already exists."""
        schema, session_key = test_session
        learner = PatternLearner(schema)

        # Add 5 header examples
        for i in range(5):
            schema.examples.insert(
                {
                    "_key": f"header_dup_{i}",
                    "session_key": session_key,
                    "element_type": "header",
                    "human_verdict": "correct",
                }
            )

        # Create an existing pattern
        schema.patterns.insert(
            {
                "_key": "test-pattern-preset_header_pattern",
                "preset_id": "test-pattern-preset",
                "element_type": "header",
                "active": True,
            }
        )

        result = learner.should_propose_pattern(session_key, "header", threshold=5)
        assert result is False

        # Cleanup pattern
        schema.patterns.delete("test-pattern-preset_header_pattern")


class TestFormatPatternProposal:
    """Test pattern proposal formatting for conversation."""

    def test_format_header_pattern(self):
        """Test formatting header pattern proposal."""
        learner = PatternLearner()
        proposal = PatternProposal(
            element_type="header",
            pattern_name="header_section_pattern",
            stage1_regex=r"^\d+\.\d+\s+",
            stage2_python="def validate(text, font_info):\n    if font_info.get('size', 0) >= 14:\n        return True",
            stage3_prompt="Is this a header?",
            confidence=0.85,
            learned_from=["ex1", "ex2", "ex3", "ex4", "ex5"],
            reasoning="Learned from examples",
            sample_matches=[],
            sample_non_matches=[],
        )

        result = learner.format_pattern_proposal(proposal)

        assert "Header" in result
        assert "Font size" in result
        assert "14pt" in result
        assert "85%" in result
        assert "5 examples" in result
        assert "yes/no/refine" in result.lower()

    def test_format_table_pattern(self):
        """Test formatting table pattern proposal."""
        learner = PatternLearner()
        proposal = PatternProposal(
            element_type="table",
            pattern_name="table_bordered_pattern",
            stage1_regex=None,
            stage2_python="def validate(t, c):\n    params = {'flavor': 'lattice'}",
            stage3_prompt="Is this a table?",
            confidence=0.9,
            learned_from=["ex1", "ex2", "ex3"],
            reasoning="Learned from examples",
            sample_matches=[],
            sample_non_matches=[],
        )

        result = learner.format_pattern_proposal(proposal)

        assert "Table" in result
        assert "bordered" in result.lower() or "grid" in result.lower()
        assert "90%" in result


class TestApplyHumanRefinement:
    """Test applying human refinements to patterns."""

    def test_start_of_line_refinement(self):
        """Test 'start of line' refinement adds ^ anchor."""
        learner = PatternLearner()
        proposal = PatternProposal(
            element_type="header",
            pattern_name="test",
            stage1_regex=r"\d+\.\d+",
            stage2_python="def v(): pass",
            stage3_prompt="Test",
            confidence=0.8,
            learned_from=[],
            reasoning="",
            sample_matches=[],
            sample_non_matches=[],
        )

        refined = learner.apply_human_refinement(proposal, "only if it's at the start of a line")

        assert refined.stage1_regex.startswith("^")

    def test_size_refinement(self):
        """Test font size refinement updates stage2."""
        learner = PatternLearner()
        proposal = PatternProposal(
            element_type="header",
            pattern_name="test",
            stage1_regex=None,
            stage2_python="def v():\n    if font_info.get('size', 0) >= 12:\n        pass",
            stage3_prompt="Test",
            confidence=0.8,
            learned_from=[],
            reasoning="",
            sample_matches=[],
            sample_non_matches=[],
        )

        refined = learner.apply_human_refinement(proposal, "font size should be at least 16pt")

        assert "16" in refined.stage2_python

    def test_condition_refinement_adds_note(self):
        """Test 'only if' refinement adds note to prompt."""
        learner = PatternLearner()
        proposal = PatternProposal(
            element_type="header",
            pattern_name="test",
            stage1_regex=None,
            stage2_python="def v(): pass",
            stage3_prompt="Is this a header?",
            confidence=0.8,
            learned_from=[],
            reasoning="",
            sample_matches=[],
            sample_non_matches=[],
        )

        refined = learner.apply_human_refinement(proposal, "only if followed by body text")

        assert "body text" in refined.stage3_prompt
