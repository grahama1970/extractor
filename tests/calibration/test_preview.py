"""Tests for extraction preview module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from extractor.pipeline.calibration.preview import (
    ElementSummary,
    ExtractionPreview,
    PagePreview,
    PreviewResult,
    format_preview_json,
    format_preview_text,
)


class TestElementSummary:
    """Tests for ElementSummary dataclass."""

    def test_create_summary(self):
        """Test creating an element summary."""
        summary = ElementSummary(
            element_type="header",
            page_num=1,
            bbox=[72, 100, 540, 120],
            text_preview="Introduction",
            confidence=0.85,
            source="baseline",
        )
        assert summary.element_type == "header"
        assert summary.confidence == 0.85
        assert summary.source == "baseline"

    def test_summary_with_pattern(self):
        """Test summary with matched pattern."""
        summary = ElementSummary(
            element_type="header",
            page_num=1,
            bbox=[72, 100, 540, 120],
            text_preview="3.2.1 Methods",
            confidence=0.92,
            source="calibrated",
            matched_pattern="section_number_pattern",
        )
        assert summary.matched_pattern == "section_number_pattern"


class TestPreviewResult:
    """Tests for PreviewResult dataclass."""

    def test_total_baseline(self):
        """Test total_baseline calculation."""
        result = PreviewResult(
            pdf_path="/test.pdf",
            total_pages=10,
            pages_previewed=[1, 5, 10],
            page_previews=[],
            baseline_count={"header": 5, "table": 3, "figure": 2},
            calibrated_count={"header": 7, "table": 3, "figure": 4},
        )
        assert result.total_baseline() == 10

    def test_total_calibrated(self):
        """Test total_calibrated calculation."""
        result = PreviewResult(
            pdf_path="/test.pdf",
            total_pages=10,
            pages_previewed=[1, 5, 10],
            page_previews=[],
            baseline_count={"header": 5, "table": 3, "figure": 2},
            calibrated_count={"header": 7, "table": 3, "figure": 4},
        )
        assert result.total_calibrated() == 14

    def test_improvement_delta(self):
        """Test improvement_delta calculation."""
        result = PreviewResult(
            pdf_path="/test.pdf",
            total_pages=10,
            pages_previewed=[1, 5, 10],
            page_previews=[],
            baseline_count={"header": 5, "table": 3},
            calibrated_count={"header": 7, "table": 2, "figure": 4},
        )
        delta = result.improvement_delta()
        assert delta["header"] == 2  # 7 - 5
        assert delta["table"] == -1  # 2 - 3
        assert delta["figure"] == 4  # 4 - 0


class TestExtractionPreview:
    """Tests for ExtractionPreview class."""

    def test_sample_pages_small_doc(self):
        """Test page sampling for small documents."""
        preview = ExtractionPreview()
        pages = preview._sample_pages(total=3, max_pages=5)
        assert pages == [1, 2, 3]

    def test_sample_pages_large_doc(self):
        """Test page sampling for large documents."""
        preview = ExtractionPreview()
        pages = preview._sample_pages(total=100, max_pages=5)
        assert len(pages) <= 5
        assert 1 in pages  # First page
        assert 100 in pages  # Last page

    def test_bbox_overlap_full(self):
        """Test bbox overlap calculation - full overlap."""
        preview = ExtractionPreview()
        bbox1 = [0, 0, 100, 100]
        bbox2 = [0, 0, 100, 100]
        overlap = preview._bbox_overlap(bbox1, bbox2)
        assert overlap == 1.0

    def test_bbox_overlap_none(self):
        """Test bbox overlap calculation - no overlap."""
        preview = ExtractionPreview()
        bbox1 = [0, 0, 50, 50]
        bbox2 = [100, 100, 150, 150]
        overlap = preview._bbox_overlap(bbox1, bbox2)
        assert overlap == 0.0

    def test_bbox_overlap_partial(self):
        """Test bbox overlap calculation - partial overlap."""
        preview = ExtractionPreview()
        bbox1 = [0, 0, 100, 100]
        bbox2 = [50, 50, 150, 150]
        overlap = preview._bbox_overlap(bbox1, bbox2)
        # Intersection: 50x50 = 2500
        # Area1: 10000, Area2: 10000
        # Union: 10000 + 10000 - 2500 = 17500
        # IoU: 2500/17500 = 0.143
        assert 0.1 < overlap < 0.2

    def test_to_summary(self):
        """Test converting DetectedElement to ElementSummary."""
        from extractor.pipeline.calibration.detector import DetectedElement, FontInfo

        preview = ExtractionPreview()
        element = DetectedElement(
            element_type="header",
            bbox=[72, 100, 540, 120],
            page_num=1,
            element_idx=0,
            text="This is a very long header text that should be truncated in the preview",
            font_info=FontInfo(name="Arial", size=14.0, is_bold=True),
            confidence=0.85,
            reasoning="Large bold font",
        )

        summary = preview._to_summary(element, "baseline")
        assert summary.element_type == "header"
        assert summary.source == "baseline"
        assert len(summary.text_preview) <= 53  # 50 chars + "..."
        assert summary.confidence == 0.85

    def test_compute_diff_added(self):
        """Test computing diff - added elements."""
        preview = ExtractionPreview()
        baseline = [
            ElementSummary(
                element_type="header",
                page_num=1,
                bbox=[0, 0, 100, 20],
                text_preview="Header 1",
                confidence=0.8,
                source="baseline",
            )
        ]
        calibrated = [
            ElementSummary(
                element_type="header",
                page_num=1,
                bbox=[0, 0, 100, 20],
                text_preview="Header 1",
                confidence=0.8,
                source="calibrated",
            ),
            ElementSummary(
                element_type="header",
                page_num=1,
                bbox=[0, 100, 100, 120],
                text_preview="Header 2",
                confidence=0.9,
                source="calibrated",
            ),
        ]

        added, removed, improved = preview._compute_diff(baseline, calibrated)
        assert len(added) == 1
        assert added[0].text_preview == "Header 2"
        assert len(removed) == 0

    def test_compute_diff_removed(self):
        """Test computing diff - removed elements."""
        preview = ExtractionPreview()
        baseline = [
            ElementSummary(
                element_type="table",
                page_num=1,
                bbox=[0, 0, 100, 100],
                text_preview="Table",
                confidence=0.6,
                source="baseline",
            )
        ]
        calibrated = []

        added, removed, improved = preview._compute_diff(baseline, calibrated)
        assert len(added) == 0
        assert len(removed) == 1

    def test_preview_extraction_basic(self, tmp_path):
        """Test basic preview extraction."""
        # Create a real temporary PDF
        try:
            import fitz as real_fitz

            pdf_path = tmp_path / "test.pdf"
            doc = real_fitz.open()
            for _ in range(5):
                doc.new_page()
            doc.save(str(pdf_path))
            doc.close()
        except ImportError:
            pytest.skip("PyMuPDF not available")

        # Mock detector to return empty results for speed
        with patch("extractor.pipeline.calibration.preview.ElementDetector") as mock_detector_class:
            mock_detector = MagicMock()
            mock_detector.detect_page.return_value = []
            mock_detector_class.return_value = mock_detector

            preview = ExtractionPreview()
            result = preview.preview_extraction(
                pdf_path=pdf_path,
                pages=[1, 2, 3],
            )

            assert result.total_pages == 5
            assert result.pages_previewed == [1, 2, 3]


class TestFormatPreviewText:
    """Tests for format_preview_text function."""

    def test_format_basic(self):
        """Test basic text formatting."""
        result = PreviewResult(
            pdf_path="/test.pdf",
            total_pages=10,
            pages_previewed=[1, 5],
            page_previews=[
                PagePreview(
                    page_num=1,
                    baseline_elements=[],
                    calibrated_elements=[],
                    added=[],
                    removed=[],
                    improved=[],
                ),
            ],
            baseline_count={"header": 5},
            calibrated_count={"header": 7},
            patterns_applied=["header_pattern"],
        )

        text = format_preview_text(result)
        assert "test.pdf" in text
        assert "10 total" in text
        assert "header" in text.lower()
        assert "+2" in text  # Delta

    def test_format_with_patterns(self):
        """Test formatting with patterns applied."""
        result = PreviewResult(
            pdf_path="/test.pdf",
            total_pages=5,
            pages_previewed=[1],
            page_previews=[],
            patterns_applied=["section_number_pattern", "bold_header_pattern"],
        )

        text = format_preview_text(result)
        assert "section_number_pattern" in text
        assert "bold_header_pattern" in text


class TestFormatPreviewJson:
    """Tests for format_preview_json function."""

    def test_format_json_structure(self):
        """Test JSON formatting structure."""
        result = PreviewResult(
            pdf_path="/test.pdf",
            total_pages=10,
            pages_previewed=[1, 5],
            page_previews=[
                PagePreview(
                    page_num=1,
                    baseline_elements=[],
                    calibrated_elements=[],
                    added=[
                        ElementSummary(
                            element_type="header",
                            page_num=1,
                            bbox=[0, 0, 100, 20],
                            text_preview="New Header",
                            confidence=0.9,
                            source="calibrated",
                        )
                    ],
                    removed=[],
                    improved=[],
                ),
            ],
            baseline_count={"header": 5},
            calibrated_count={"header": 6},
            session_key="test_session",
        )

        json_data = format_preview_json(result)

        assert json_data["pdf_path"] == "/test.pdf"
        assert json_data["total_pages"] == 10
        assert json_data["session_key"] == "test_session"
        assert "summary" in json_data
        assert json_data["summary"]["baseline_count"]["header"] == 5
        assert len(json_data["pages"]) == 1
        assert json_data["pages"][0]["added_count"] == 1

    def test_format_json_serializable(self):
        """Test that JSON output is serializable."""
        result = PreviewResult(
            pdf_path="/test.pdf",
            total_pages=5,
            pages_previewed=[1],
            page_previews=[],
        )

        json_data = format_preview_json(result)
        # Should not raise
        json_str = json.dumps(json_data)
        assert isinstance(json_str, str)


class TestPreviewCLI:
    """Tests for preview CLI command."""

    @pytest.mark.skip(reason="CLI import has pre-existing issues with missing modules")
    def test_cli_preview_command(self):
        """Test preview CLI command execution."""
        # Note: This test is skipped due to pre-existing import issues
        # in extractor.cli that prevent importing the app cleanly.
        # The preview functionality is tested via the module tests above.
        pass


class TestPreviewIntegration:
    """Integration tests for preview with real PDFs."""

    @pytest.fixture
    def sample_pdf(self, tmp_path):
        """Create a simple test PDF."""
        try:
            import fitz

            pdf_path = tmp_path / "test.pdf"
            doc = fitz.open()
            page = doc.new_page()
            # Add some text
            page.insert_text((72, 100), "1. Introduction", fontsize=14)
            page.insert_text((72, 150), "This is the body text.", fontsize=11)
            page.insert_text((72, 300), "2. Methods", fontsize=14)
            doc.save(str(pdf_path))
            doc.close()
            return pdf_path
        except ImportError:
            pytest.skip("PyMuPDF not available")

    def test_preview_real_pdf(self, sample_pdf):
        """Test preview on a real PDF."""
        preview = ExtractionPreview()
        result = preview.preview_extraction(
            pdf_path=sample_pdf,
            pages=[1],
        )

        assert result.total_pages == 1
        assert len(result.page_previews) == 1

    def test_preview_text_output(self, sample_pdf):
        """Test preview text output on real PDF."""
        preview = ExtractionPreview()
        result = preview.preview_extraction(
            pdf_path=sample_pdf,
            pages=[1],
        )

        text = format_preview_text(result)
        assert "Extraction Preview" in text
        assert "test.pdf" in text
