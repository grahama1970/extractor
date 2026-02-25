"""Tests for verbose preset detection in S00.

These tests verify that match_preset with verbose=True:
1. Tracks keyword matches with context
2. Tracks filename trigger matches
3. Reports layout match/mismatch correctly
4. Generates accurate selection_reason
"""

import pytest
from extractor.pipeline.steps.s00_profile_detector import match_preset


class TestVerboseKeywordTracking:
    """Test keyword tracking in verbose mode."""

    def test_keyword_matches_tracked(self):
        """Keywords found in text should be tracked with context."""
        analysis = {
            "full_text_sample": "This is an arXiv paper with Abstract and Introduction sections.",
            "has_multi_column": True,
        }
        result = match_preset(analysis, "test.pdf", verbose=True)

        assert "match_details" in result
        arxiv_details = result["match_details"].get("arxiv", {})
        assert arxiv_details.get("keyword_matches")
        keywords_found = [m["keyword"] for m in arxiv_details["keyword_matches"]]
        assert "arXiv" in keywords_found or "Abstract" in keywords_found

    def test_keyword_context_captured(self):
        """Keyword matches should include surrounding context."""
        analysis = {
            "full_text_sample": "The full Abstract of this paper discusses machine learning.",
            "has_multi_column": False,
        }
        result = match_preset(analysis, "paper.pdf", verbose=True)

        arxiv_details = result["match_details"].get("arxiv", {})
        if arxiv_details.get("keyword_matches"):
            match = arxiv_details["keyword_matches"][0]
            assert "context" in match
            assert len(match["context"]) > 0


class TestFilenameTriggerDetection:
    """Test filename trigger tracking."""

    def test_filename_trigger_tracked(self):
        """Filename triggers should be captured."""
        analysis = {"full_text_sample": "", "has_multi_column": False}
        result = match_preset(analysis, "2501_12345.pdf", verbose=True)

        arxiv_details = result["match_details"].get("arxiv_scientific", {})
        assert "2501" in arxiv_details.get("filename_triggers", [])

    def test_multiple_filename_triggers(self):
        """Multiple matching triggers should all be tracked."""
        analysis = {"full_text_sample": "", "has_multi_column": False}
        result = match_preset(analysis, "arxiv_2501_paper.pdf", verbose=True)

        arxiv_details = result["match_details"].get("arxiv_scientific", {})
        triggers = arxiv_details.get("filename_triggers", [])
        # Should match both "arxiv" and "2501"
        assert len(triggers) >= 2


class TestLayoutMatchReporting:
    """Test layout match/mismatch reporting."""

    def test_double_column_match(self):
        """Double-column preset with multi-column doc should report match."""
        analysis = {"full_text_sample": "", "has_multi_column": True}
        result = match_preset(analysis, "paper.pdf", verbose=True)

        arxiv_details = result["match_details"].get("arxiv", {})
        assert "matched" in arxiv_details.get("layout_match", "")

    def test_single_column_match(self):
        """Single-column preset with single-column doc should report match."""
        analysis = {"full_text_sample": "", "has_multi_column": False}
        result = match_preset(analysis, "test.pdf", verbose=True)

        req_details = result["match_details"].get("requirements_spec", {})
        assert "matched" in req_details.get("layout_match", "")

    def test_layout_mismatch(self):
        """Mismatch should be reported with details."""
        analysis = {"full_text_sample": "", "has_multi_column": False}
        result = match_preset(analysis, "test.pdf", verbose=True)

        arxiv_details = result["match_details"].get("arxiv", {})
        assert "mismatch" in arxiv_details.get("layout_match", "")


class TestSelectionReasonFormat:
    """Test selection_reason generation."""

    def test_selection_reason_includes_keywords(self):
        """Selection reason should mention keyword matches."""
        analysis = {
            "full_text_sample": "arXiv Abstract Introduction References Theorem",
            "has_multi_column": True,
        }
        result = match_preset(analysis, "2501_test.pdf", verbose=True)

        assert "selection_reason" in result
        assert "keyword" in result["selection_reason"].lower()

    def test_selection_reason_includes_filename(self):
        """Selection reason should mention filename triggers when matched."""
        analysis = {"full_text_sample": "", "has_multi_column": False}
        result = match_preset(analysis, "2501_test.pdf", verbose=True)

        if result["matched"]:
            assert "filename" in result["selection_reason"].lower() or "2501" in result["selection_reason"]

    def test_no_match_reason(self):
        """When no preset matches, reason should explain."""
        analysis = {"full_text_sample": "random text with no keywords", "has_multi_column": False}
        result = match_preset(analysis, "random.pdf", verbose=True)

        if not result["matched"]:
            assert "no preset" in result["selection_reason"].lower() or "threshold" in result["selection_reason"].lower()


class TestScoreCalculation:
    """Test that scores are correctly calculated and reported."""

    def test_final_score_matches_all_scores(self):
        """final_score in details should match all_scores."""
        analysis = {"full_text_sample": "arXiv paper", "has_multi_column": True}
        result = match_preset(analysis, "test.pdf", verbose=True)

        for name, score in result["all_scores"].items():
            details = result["match_details"].get(name, {})
            assert details.get("final_score") == score

    def test_min_score_tracked(self):
        """min_score_required should be tracked for each preset."""
        analysis = {"full_text_sample": "", "has_multi_column": False}
        result = match_preset(analysis, "test.pdf", verbose=True)

        for name, details in result["match_details"].items():
            assert "min_score_required" in details
            assert isinstance(details["min_score_required"], int)


class TestNonVerboseMode:
    """Test that non-verbose mode still works correctly."""

    def test_non_verbose_returns_basic_result(self):
        """Without verbose=True, result should not include match_details."""
        analysis = {"full_text_sample": "arXiv paper", "has_multi_column": True}
        result = match_preset(analysis, "test.pdf", verbose=False)

        assert "matched" in result
        assert "all_scores" in result
        assert "match_details" not in result
        assert "selection_reason" not in result

    def test_default_is_non_verbose(self):
        """Default behavior should be non-verbose."""
        analysis = {"full_text_sample": "arXiv paper", "has_multi_column": True}
        result = match_preset(analysis, "test.pdf")  # No verbose arg

        assert "match_details" not in result
