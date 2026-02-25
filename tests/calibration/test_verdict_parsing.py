"""Tests for natural language verdict parsing.

Task 6: Parse human feedback into structured verdicts.
"""

import pytest

from extractor.pipeline.calibration import HumanVerdict
from extractor.pipeline.calibration.verdict_parser import (
    parse_verdict,
)


class TestCorrectVerdicts:
    """Test parsing of CORRECT verdicts."""

    @pytest.mark.parametrize(
        "text",
        [
            "correct",
            "yes",
            "good",
            "looks good",
            "that's right",
            "yes, correct",
            "yep",
            "correct!",
            "Yes, that's correct",
            "Looks good to me",
        ],
    )
    def test_correct_phrasings(self, text):
        """Test common phrasings for CORRECT verdict."""
        result = parse_verdict(text)
        assert result.verdict == HumanVerdict.CORRECT
        assert result.correction is None


class TestWrongTypeVerdicts:
    """Test parsing of WRONG_TYPE verdicts with type extraction."""

    @pytest.mark.parametrize(
        "text,expected_type",
        [
            ("that's a figure", "figure"),
            ("no, it's a table", "table"),
            ("wrong, that's a header", "header"),
            ("this is actually a figure", "figure"),
            ("it's a figure, not a table", "figure"),
            ("That's a Figure", "figure"),  # Case insensitive
            ("wrong type - should be table", "table"),
        ],
    )
    def test_wrong_type_with_correction(self, text, expected_type):
        """Test extraction of correct type from wrong_type verdicts."""
        result = parse_verdict(text)
        assert result.verdict == HumanVerdict.WRONG_TYPE
        assert result.correction is not None
        assert result.correction.get("correct_type", "").lower() == expected_type


class TestNotElementVerdicts:
    """Test parsing of NOT_ELEMENT verdicts."""

    @pytest.mark.parametrize(
        "text",
        [
            "not an element",
            "ignore this",
            "false positive",
            "that's not an element",
            "this is just body text",
            "not a real element",
            "ignore",
            "this is emphasis, not a header",
        ],
    )
    def test_not_element_phrasings(self, text):
        """Test common phrasings for NOT_ELEMENT verdict."""
        result = parse_verdict(text)
        assert result.verdict == HumanVerdict.NOT_ELEMENT


class TestSplitVerdicts:
    """Test parsing of SPLIT verdicts."""

    @pytest.mark.parametrize(
        "text",
        [
            "split this",
            "two elements",
            "there are two elements here",
            "this should be split",
            "split into two",
            "multiple elements",
        ],
    )
    def test_split_phrasings(self, text):
        """Test common phrasings for SPLIT verdict."""
        result = parse_verdict(text)
        assert result.verdict == HumanVerdict.SPLIT


class TestFlaggedVerdicts:
    """Test parsing of FLAGGED verdicts."""

    @pytest.mark.parametrize(
        "text",
        [
            "flag this",
            "unsure",
            "not sure",
            "I'm not sure",
            "ask expert",
            "need help",
            "flag for review",
            "come back to this",
        ],
    )
    def test_flagged_phrasings(self, text):
        """Test common phrasings for FLAGGED verdict."""
        result = parse_verdict(text)
        assert result.verdict == HumanVerdict.FLAGGED


class TestNoteExtraction:
    """Test extraction of explanatory notes from verdicts."""

    def test_note_after_dash(self):
        """Test note extraction after dash."""
        result = parse_verdict("wrong - it's actually a wiring diagram")
        assert result.note is not None
        assert "wiring diagram" in result.note.lower()

    def test_note_in_parentheses(self):
        """Test note extraction from parentheses."""
        result = parse_verdict("correct (but bbox is slightly off)")
        assert result.note is not None
        assert "bbox" in result.note.lower()

    def test_note_because(self):
        """Test note extraction after 'because'."""
        result = parse_verdict("not an element because it's just emphasis")
        assert result.note is not None
        assert "emphasis" in result.note.lower()


class TestAdjustBboxVerdicts:
    """Test parsing of bbox adjustment requests."""

    @pytest.mark.parametrize(
        "text",
        [
            "adjust bbox",
            "bbox is too small",
            "too small",
            "too big",
            "extend the bbox",
            "bbox cuts off the right side",
            "include the caption",
        ],
    )
    def test_adjust_bbox_phrasings(self, text):
        """Test common phrasings for ADJUST_BBOX verdict."""
        result = parse_verdict(text)
        assert result.verdict == HumanVerdict.ADJUST_BBOX


class TestEdgeCases:
    """Test edge cases and ambiguous inputs."""

    def test_empty_string(self):
        """Test empty string defaults to FLAGGED."""
        result = parse_verdict("")
        assert result.verdict == HumanVerdict.FLAGGED

    def test_whitespace_only(self):
        """Test whitespace-only defaults to FLAGGED."""
        result = parse_verdict("   ")
        assert result.verdict == HumanVerdict.FLAGGED

    def test_ambiguous_defaults_to_flagged(self):
        """Test ambiguous input defaults to FLAGGED."""
        result = parse_verdict("hmm interesting")
        assert result.verdict == HumanVerdict.FLAGGED
