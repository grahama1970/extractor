"""Tests for S00 font-based section estimation."""

import json
from pathlib import Path

import pytest

try:
    import fitz

    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

from extractor.pipeline.steps.s00_profile_detector import (
    _build_hierarchy,
    estimate_section_count_by_font,
)


def _make_pdf(tmp_path: Path, body_size: float = 10.0, heading_size: float = 14.0,
              num_headings: int = 5, num_body_lines: int = 20) -> Path:
    """Create a synthetic PDF with known font sizes for testing."""
    doc = fitz.open()

    page = doc.new_page()
    y = 72  # start 1 inch from top

    for i in range(num_headings):
        # Insert heading
        page.insert_text(
            (72, y),
            f"Section {i + 1}: Heading Text",
            fontsize=heading_size,
            fontname="helv",
        )
        y += heading_size + 4

        # Insert body lines
        for j in range(num_body_lines // num_headings):
            page.insert_text(
                (72, y),
                f"This is body text line {j + 1} under section {i + 1} with enough words.",
                fontsize=body_size,
                fontname="helv",
            )
            y += body_size + 2

            # New page if we run out of space
            if y > 750:
                page = doc.new_page()
                y = 72

    pdf_path = tmp_path / "test_fonts.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.mark.skipif(not HAS_FITZ, reason="PyMuPDF (fitz) not available")
class TestFontSectionEstimate:
    def test_detects_headings_by_size(self, tmp_path):
        """Headings at 14pt with 10pt body should be detected."""
        pdf = _make_pdf(tmp_path, body_size=10.0, heading_size=14.0, num_headings=5)
        result = estimate_section_count_by_font(pdf)

        assert result["estimated_count"] >= 3  # should find most headings
        assert result["body_font_size"] == 10.0
        assert result["pages_sampled"] > 0

    def test_no_headings_when_uniform_size(self, tmp_path):
        """All text at same size should produce zero or near-zero headings."""
        pdf = _make_pdf(tmp_path, body_size=10.0, heading_size=10.0, num_headings=5)
        result = estimate_section_count_by_font(pdf)

        # With uniform font, no headings should be detected
        assert result["estimated_count"] <= 1

    def test_small_body_font_minimum_threshold(self, tmp_path):
        """Documents with 8pt body text should still detect larger headings."""
        pdf = _make_pdf(tmp_path, body_size=8.0, heading_size=14.0,
                        num_headings=3, num_body_lines=30)
        result = estimate_section_count_by_font(pdf)

        # Should detect headings at 14pt with 8pt body
        assert result["estimated_count"] >= 2
        assert result["body_font_size"] == 8.0

    def test_graceful_on_missing_fitz(self, tmp_path):
        """Function returns zero counts when fitz is not available."""
        import extractor.pipeline.steps.s00_profile_detector as mod

        # Temporarily disable fitz
        orig = mod._HAVE_FITZ
        mod._HAVE_FITZ = False
        try:
            result = estimate_section_count_by_font(tmp_path / "nonexistent.pdf")
            assert result["estimated_count"] == 0
            assert "error" in result
        finally:
            mod._HAVE_FITZ = orig

    def test_nonexistent_pdf_returns_zero(self, tmp_path):
        """Missing PDF returns zero gracefully."""
        result = estimate_section_count_by_font(tmp_path / "missing.pdf")
        assert result["estimated_count"] == 0
        assert "error" in result


def _make_academic_pdf(tmp_path: Path, body_size: float = 10.0,
                       num_sections: int = 6) -> Path:
    """Create a PDF mimicking an academic paper: same-size bold headings.

    This is the pattern seen in arxiv papers where body=10pt and headings
    are also 10pt but bold, with section numbering (1 Introduction, 2 Methods).
    """
    doc = fitz.open()
    page = doc.new_page()
    y = 72

    for i in range(num_sections):
        # Bold heading at SAME size as body
        page.insert_text(
            (72, y),
            f"{i + 1} Section Title Number {i + 1}",
            fontsize=body_size,
            fontname="hebo",  # Helvetica Bold
        )
        y += body_size + 6

        # Body text (6 lines per section)
        for j in range(6):
            page.insert_text(
                (72, y),
                f"This is regular body text in paragraph {j + 1} of section {i + 1} "
                f"providing sufficient content.",
                fontsize=body_size,
                fontname="helv",  # Helvetica Regular
            )
            y += body_size + 2
            if y > 750:
                page = doc.new_page()
                y = 72

    pdf_path = tmp_path / "test_academic.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.mark.skipif(not HAS_FITZ, reason="PyMuPDF (fitz) not available")
class TestBoldOnlyHeadingDetection:
    """Tests for same-size bold heading detection (academic paper pattern)."""

    def test_detects_bold_headings_with_section_numbers(self, tmp_path):
        """Bold headings with section numbers (e.g., '1 Introduction') at same
        font size as body should be detected."""
        pdf = _make_academic_pdf(tmp_path, body_size=10.0, num_sections=6)
        result = estimate_section_count_by_font(pdf)

        # Should detect most of the bold headings
        assert result["estimated_count"] >= 4, (
            f"Expected >=4 bold headings, got {result['estimated_count']}"
        )
        assert result["body_font_size"] == 10.0

    def test_does_not_detect_non_bold_same_size_text(self, tmp_path):
        """Regular (non-bold) text at same font size should NOT be detected."""
        # _make_pdf uses regular font for both headings and body when sizes match
        pdf = _make_pdf(tmp_path, body_size=10.0, heading_size=10.0, num_headings=5)
        result = estimate_section_count_by_font(pdf)

        # Should NOT detect regular-weight text as headings
        assert result["estimated_count"] <= 2

    def test_academic_paper_body_font_detection(self, tmp_path):
        """Body font size should be correctly detected in academic-style PDFs."""
        pdf = _make_academic_pdf(tmp_path, body_size=9.5, num_sections=4)
        result = estimate_section_count_by_font(pdf)

        assert result["body_font_size"] == 9.5


class TestBuildHierarchy:
    def test_max_of_regex_and_font(self):
        """Combined estimate should be max(regex, font)."""
        analysis = {
            "section_style": "decimal",
            "section_estimate": {"estimated_count": 10, "by_pattern": {"decimal": 10}},
            "font_section_estimate": {"estimated_count": 25, "body_font_size": 10.0},
        }
        h = _build_hierarchy(analysis)

        assert h["estimated_sections"] == 25  # font wins
        assert h["estimated_sections_regex"] == 10
        assert h["estimated_sections_font"] == 25

    def test_regex_wins_when_higher(self):
        """Regex estimate should win when higher than font."""
        analysis = {
            "section_style": "decimal",
            "section_estimate": {"estimated_count": 50, "by_pattern": {"decimal": 50}},
            "font_section_estimate": {"estimated_count": 20, "body_font_size": 12.0},
        }
        h = _build_hierarchy(analysis)

        assert h["estimated_sections"] == 50  # regex wins

    def test_missing_font_estimate(self):
        """Missing font estimate should fall back to regex."""
        analysis = {
            "section_style": None,
            "section_estimate": {"estimated_count": 5, "by_pattern": {}},
        }
        h = _build_hierarchy(analysis)

        assert h["estimated_sections"] == 5
        assert h["estimated_sections_font"] == 0
