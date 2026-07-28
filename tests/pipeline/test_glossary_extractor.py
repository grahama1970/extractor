"""
Unit tests for glossary entry extraction and content verification.

Tests the heuristic extractor and verify_glossary_content() without
requiring /assistant or ArangoDB.
"""

import pytest

from extractor.pipeline.utils.glossary_extractor import (
    _heuristic_extract,
    extract_glossary_entries,
    verify_glossary_content,
)
from extractor.pipeline.steps.s04_section_builder import _keyword_is_glossary


# ---------------------------------------------------------------------------
# Heuristic extraction tests
# ---------------------------------------------------------------------------

class TestHeuristicExtract:
    """Test Tier 0 structural regex extraction."""

    def test_dash_separated(self):
        """Extract terms and their definitions from a dash-separated text."""
        text = (
            "BHT - Bell Helicopter Textron\n"
            "REQ - Requirement Document\n"
            "TBD - To Be Determined\n"
            "CDR - Critical Design Review\n"
        )
        entries = _heuristic_extract(text)
        assert len(entries) >= 3
        terms = {e["term"] for e in entries}
        assert "BHT" in terms
        assert "REQ" in terms

    def test_colon_separated(self):
        """Test extraction of colon-separated key-value pairs."""
        text = (
            "BHT: Bell Helicopter Textron Inc.\n"
            "REQ: Requirement as defined by the program\n"
            "TBD: To Be Determined by the review board\n"
        )
        entries = _heuristic_extract(text)
        assert len(entries) >= 3

    def test_tab_separated(self):
        """Verify tab-separated entry extraction."""
        text = (
            "BHT\tBell Helicopter Textron Inc.\n"
            "REQ\tRequirement Document Reference\n"
            "TBD\tTo Be Determined Later\n"
        )
        entries = _heuristic_extract(text)
        assert len(entries) >= 3

    def test_wide_space_separated(self):
        """Extract entries from a wide space-separated text block."""
        text = (
            "BHT     Bell Helicopter Textron Inc.\n"
            "REQ     Requirement Document Reference\n"
            "TBD     To Be Determined by the review board\n"
        )
        entries = _heuristic_extract(text)
        assert len(entries) >= 3

    def test_em_dash_separated(self):
        """Test extraction of em-dash separated entries."""
        text = (
            "BHT — Bell Helicopter Textron Inc.\n"
            "REQ — Requirement Document Reference\n"
            "TBD — To Be Determined by the board\n"
        )
        entries = _heuristic_extract(text)
        assert len(entries) >= 3

    def test_deduplication(self):
        """Verify deduplication of heuristic-extracted entries."""
        text = (
            "REQ - Requirement\n"
            "REQ - Requirement\n"
            "TBD - To Be Determined\n"
        )
        entries = _heuristic_extract(text)
        req_count = sum(1 for e in entries if e["term"] == "REQ")
        assert req_count == 1

    def test_category_detection(self):
        """Verify term category detection."""
        text = (
            "REQ - Requirement\n"
            "TBD - To Be Determined\n"
            "Baseline - The approved configuration at a specific point in time\n"
        )
        entries = _heuristic_extract(text)
        categories = {e["term"]: e["category"] for e in entries}
        assert categories.get("REQ") == "acronym"  # All-caps short term
        assert categories.get("Baseline") == "definition"  # Mixed case

    def test_empty_input(self):
        """Extract non-empty elements from a string, returning an empty list."""
        assert _heuristic_extract("") == []
        assert _heuristic_extract("   ") == []

    def test_non_glossary_text(self):
        """Extract entries from text, returning an empty list for non-glossary."""
        text = "This is a normal paragraph about engineering processes."
        entries = _heuristic_extract(text)
        assert len(entries) == 0


# ---------------------------------------------------------------------------
# Public API tests
# ---------------------------------------------------------------------------

class TestExtractGlossaryEntries:
    """Test the full extraction pipeline (heuristic path)."""

    def test_sufficient_heuristic_entries(self):
        """Check if extracted glossary entries meet minimum count requirement."""
        text = (
            "BHT - Bell Helicopter Textron\n"
            "REQ - Requirement Document\n"
            "TBD - To Be Determined\n"
            "CDR - Critical Design Review\n"
        )
        entries = extract_glossary_entries(text)
        assert len(entries) >= 3

    def test_empty_returns_empty(self):
        """Extract glossary entries from a string or None, returning an empty list."""
        assert extract_glossary_entries("") == []
        assert extract_glossary_entries(None) == []


# ---------------------------------------------------------------------------
# Content verification tests
# ---------------------------------------------------------------------------

class TestVerifyGlossaryContent:
    """Test verify_glossary_content() used by S04."""

    def test_valid_glossary(self):
        """Test valid glossary content verification."""
        text = (
            "BHT - Bell Helicopter Textron\n"
            "REQ - Requirement Document\n"
            "TBD - To Be Determined\n"
            "CDR - Critical Design Review\n"
        )
        assert verify_glossary_content(text) is True

    def test_insufficient_entries(self):
        """Verify glossary content for insufficient entries."""
        text = "BHT - Bell Helicopter Textron\n"
        assert verify_glossary_content(text) is False

    def test_non_glossary_text(self):
        """Check if text contains glossary content."""
        text = "This document describes the system requirements for the program."
        assert verify_glossary_content(text) is False

    def test_custom_min_pairs(self):
        """Verify glossary content against minimum required pairs."""
        text = (
            "BHT - Bell Helicopter Textron\n"
            "REQ - Requirement Document\n"
        )
        assert verify_glossary_content(text, min_pairs=2) is True
        assert verify_glossary_content(text, min_pairs=3) is False


# ---------------------------------------------------------------------------
# S04 keyword detection (backward compat)
# ---------------------------------------------------------------------------

class TestKeywordIsGlossary:
    """Test keyword-based glossary detection from S04."""

    def test_exact_matches(self):
        """Check if a keyword matches glossary terms."""
        assert _keyword_is_glossary("Acronyms and Definitions") is True
        assert _keyword_is_glossary("GLOSSARY") is True
        assert _keyword_is_glossary("List of Abbreviations") is True
        assert _keyword_is_glossary("Nomenclature") is True

    def test_negative(self):
        """Assert common strings are not identified as glossary keywords."""
        assert _keyword_is_glossary("Introduction") is False
        assert _keyword_is_glossary("Test Results") is False
        assert _keyword_is_glossary("") is False


# ---------------------------------------------------------------------------
# S04 _is_glossary_section with content verification
# ---------------------------------------------------------------------------

class TestIsGlossarySection:
    """Test the upgraded _is_glossary_section with content verification."""

    def test_keyword_match_with_content(self):
        """Test glossary section detection using title and content."""
        from extractor.pipeline.steps.s04_section_builder import _is_glossary_section
        content = (
            "BHT - Bell Helicopter Textron\n"
            "REQ - Requirement Document\n"
            "TBD - To Be Determined\n"
        )
        assert _is_glossary_section("Acronyms and Definitions", content) is True

    def test_keyword_match_no_content(self):
        """Validate keyword matching for a glossary section title."""
        from extractor.pipeline.steps.s04_section_builder import _is_glossary_section
        assert _is_glossary_section("Acronyms and Definitions") is True

    def test_keyword_match_bad_content(self):
        """Assert `_is_glossary_section` rejects non-glossary content despite title."""
        from extractor.pipeline.steps.s04_section_builder import _is_glossary_section
        # Title matches but content is not a glossary
        assert _is_glossary_section("Acronyms and Definitions", "Regular paragraph text.") is False

    def test_no_match(self):
        """Test _is_glossary_section does not identify non-glossary text."""
        from extractor.pipeline.steps.s04_section_builder import _is_glossary_section
        assert _is_glossary_section("Introduction") is False
