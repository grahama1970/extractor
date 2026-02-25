"""Tests for element detection with style metadata.

These tests verify the detector extracts elements with font/style info.
"""

from unittest.mock import MagicMock, patch

import pytest

from extractor.pipeline.calibration.detector import (
    DetectedElement,
    DetectorConfig,
    ElementDetector,
    FontInfo,
    detect_elements,
)


@pytest.fixture
def mock_page():
    """Create a mock PyMuPDF page with various elements."""
    page = MagicMock()

    # Mock blocks with headers and text
    blocks = [
        # Header block
        {
            "type": 0,
            "bbox": [72, 50, 400, 70],
            "lines": [
                {
                    "bbox": [72, 50, 400, 70],
                    "spans": [
                        {
                            "text": "1.2 Requirements Section",
                            "flags": 16,  # Bold
                            "size": 14,
                            "font": "Arial-Bold",
                            "color": 0x003366,
                        }
                    ],
                }
            ],
        },
        # Table-like structure (multiple columns)
        {
            "type": 0,
            "bbox": [72, 100, 200, 120],
            "lines": [
                {
                    "bbox": [72, 100, 200, 120],
                    "spans": [
                        {"text": "Column 1", "flags": 0, "size": 10, "font": "Arial", "color": 0}
                    ],
                }
            ],
        },
        {
            "type": 0,
            "bbox": [200, 100, 300, 120],
            "lines": [
                {
                    "bbox": [200, 100, 300, 120],
                    "spans": [
                        {"text": "Column 2", "flags": 0, "size": 10, "font": "Arial", "color": 0}
                    ],
                }
            ],
        },
        {
            "type": 0,
            "bbox": [300, 100, 400, 120],
            "lines": [
                {
                    "bbox": [300, 100, 400, 120],
                    "spans": [
                        {"text": "Column 3", "flags": 0, "size": 10, "font": "Arial", "color": 0}
                    ],
                }
            ],
        },
        {
            "type": 0,
            "bbox": [72, 130, 200, 150],
            "lines": [
                {
                    "bbox": [72, 130, 200, 150],
                    "spans": [
                        {"text": "Value 1", "flags": 0, "size": 10, "font": "Arial", "color": 0}
                    ],
                }
            ],
        },
        {
            "type": 0,
            "bbox": [200, 130, 300, 150],
            "lines": [
                {
                    "bbox": [200, 130, 300, 150],
                    "spans": [
                        {"text": "Value 2", "flags": 0, "size": 10, "font": "Arial", "color": 0}
                    ],
                }
            ],
        },
        {
            "type": 0,
            "bbox": [300, 130, 400, 150],
            "lines": [
                {
                    "bbox": [300, 130, 400, 150],
                    "spans": [
                        {"text": "Value 3", "flags": 0, "size": 10, "font": "Arial", "color": 0}
                    ],
                }
            ],
        },
        # Image block
        {
            "type": 1,  # Image block
            "bbox": [72, 200, 300, 400],
        },
        # Caption
        {
            "type": 0,
            "bbox": [72, 410, 300, 430],
            "lines": [
                {
                    "bbox": [72, 410, 300, 430],
                    "spans": [
                        {
                            "text": "Figure 1: System Diagram",
                            "flags": 0,
                            "size": 9,
                            "font": "Arial",
                            "color": 0,
                        }
                    ],
                }
            ],
        },
    ]

    page.get_text.return_value = {"blocks": blocks}
    page.get_images.return_value = [(1, 0, 100, 100, 8, "DeviceRGB", "", "img1", "DCT")]
    page.get_image_rects.return_value = [[72, 200, 300, 400]]
    page.get_drawings.return_value = []
    page.annots.return_value = []

    return page


def test_extract_element_styles(mock_page):
    """Test detector returns elements with bbox, type, and font metadata."""
    detector = ElementDetector()
    elements = detector.detect_page(mock_page, page_num=0)

    assert len(elements) > 0

    # Check that all elements have required fields
    for elem in elements:
        assert isinstance(elem, DetectedElement)
        assert elem.element_type in ["header", "table", "figure"]
        assert len(elem.bbox) == 4
        assert elem.page_num == 0
        assert 0 <= elem.confidence <= 1
        assert elem.reasoning


def test_detect_headers(mock_page):
    """Test header detection with font size/color."""
    config = DetectorConfig(detect_headers=True, detect_tables=False, detect_figures=False)
    detector = ElementDetector(config)
    elements = detector.detect_page(mock_page, page_num=0)

    # Should find headers
    headers = [e for e in elements if e.element_type == "header"]
    assert len(headers) > 0

    # Check header has font info
    header = headers[0]
    assert header.font_info is not None
    assert header.font_info.size >= 11  # Should be large font
    assert "1.2" in header.text  # Section number


def test_detect_tables(mock_page):
    """Test table detection with structure info."""
    config = DetectorConfig(detect_headers=False, detect_tables=True, detect_figures=False)
    detector = ElementDetector(config)
    elements = detector.detect_page(mock_page, page_num=0)

    # Should find tables (grid-like structure)
    tables = [e for e in elements if e.element_type == "table"]
    assert len(tables) > 0

    # Check table has structure metadata
    table = tables[0]
    assert "rows" in table.metadata or "cols" in table.metadata or "grid" in table.reasoning.lower()


def test_disabled_element_types(mock_page):
    """Test detector respects disabled element types config."""
    # Disable headers
    config = DetectorConfig(disabled_types={"header"})
    detector = ElementDetector(config)
    elements = detector.detect_page(mock_page, page_num=0)

    headers = [e for e in elements if e.element_type == "header"]
    assert len(headers) == 0, "Headers should be disabled"

    # Disable all types
    config2 = DetectorConfig(disabled_types={"header", "table", "figure"})
    detector2 = ElementDetector(config2)
    elements2 = detector2.detect_page(mock_page, page_num=0)
    assert len(elements2) == 0, "All types disabled should return empty"


def test_detect_figures(mock_page):
    """Test figure detection."""
    config = DetectorConfig(detect_headers=False, detect_tables=False, detect_figures=True)
    detector = ElementDetector(config)
    elements = detector.detect_page(mock_page, page_num=0)

    figures = [e for e in elements if e.element_type == "figure"]
    assert len(figures) > 0


def test_font_info_extraction():
    """Test FontInfo dataclass."""
    info = FontInfo(
        name="Arial-Bold",
        size=14.0,
        color="#003366",
        is_bold=True,
        is_italic=False,
        flags=16,
    )
    assert info.name == "Arial-Bold"
    assert info.size == 14.0
    assert info.is_bold is True
    assert info.is_italic is False


def test_detected_element_dataclass():
    """Test DetectedElement dataclass."""
    elem = DetectedElement(
        element_type="header",
        bbox=[72, 50, 400, 70],
        page_num=0,
        element_idx=0,
        text="1.2 Test Header",
        font_info=FontInfo(name="Arial", size=14, color="#000000"),
        confidence=0.85,
        reasoning="Bold and large font",
    )
    assert elem.element_type == "header"
    assert elem.bbox == [72, 50, 400, 70]
    assert elem.text == "1.2 Test Header"
    assert elem.confidence == 0.85


def test_detector_config_defaults():
    """Test DetectorConfig default values."""
    config = DetectorConfig()
    assert config.detect_headers is True
    assert config.detect_tables is True
    assert config.detect_figures is True
    assert config.min_header_size == 11.0
    assert len(config.header_patterns) > 0
    assert len(config.disabled_types) == 0


def test_detect_document(tmp_path):
    """Test detecting elements across a document."""
    pdf_path = tmp_path / "test.pdf"
    pdf_path.touch()

    mock_doc = MagicMock()
    mock_doc.__len__ = MagicMock(return_value=3)

    # Create mock pages
    pages = []
    for i in range(3):
        page = MagicMock()
        page.get_text.return_value = {
            "blocks": [
                {
                    "type": 0,
                    "bbox": [72, 50, 400, 70],
                    "lines": [
                        {
                            "bbox": [72, 50, 400, 70],
                            "spans": [
                                {
                                    "text": f"{i+1}.0 Section",
                                    "flags": 16,
                                    "size": 14,
                                    "font": "Arial",
                                    "color": 0,
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        page.get_images.return_value = []
        page.get_drawings.return_value = []
        page.annots.return_value = []
        pages.append(page)

    mock_doc.__getitem__ = MagicMock(side_effect=lambda i: pages[i])

    with patch("extractor.pipeline.calibration.detector.fitz.open", return_value=mock_doc):
        detector = ElementDetector()
        results = detector.detect_document(pdf_path)

    # Should have results for each page
    assert len(results) > 0


def test_detect_elements_convenience(tmp_path):
    """Test convenience function."""
    assert callable(detect_elements)


def test_header_scoring():
    """Test header scoring logic."""
    detector = ElementDetector()

    # High confidence: bold, large, section pattern
    font_high = FontInfo(name="Arial-Bold", size=14, color="#003366", is_bold=True)
    score_high, _ = detector._score_header("1.2 Section Title", font_high)
    assert score_high >= 0.7

    # Low confidence: small, not bold, no pattern
    font_low = FontInfo(name="Arial", size=9, color="#000000", is_bold=False)
    score_low, _ = detector._score_header(
        "This is regular text content that goes on and on.", font_low
    )
    assert score_low < 0.5


def test_bbox_overlap():
    """Test bounding box overlap calculation."""
    detector = ElementDetector()

    # Full overlap
    overlap = detector._bbox_overlap([0, 0, 100, 100], [0, 0, 100, 100])
    assert overlap == 1.0

    # No overlap
    overlap = detector._bbox_overlap([0, 0, 50, 50], [100, 100, 200, 200])
    assert overlap == 0.0

    # Partial overlap
    overlap = detector._bbox_overlap([0, 0, 100, 100], [50, 50, 150, 150])
    assert 0 < overlap < 1
