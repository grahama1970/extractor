"""Tests for calibrate CLI commands."""

import pytest

import fitz

from extractor.pipeline.calibration import (
    CalibrationSchema,
    CalibrationSession,
    SessionStatus,
    FeedbackHandler,
    detect_elements,
)


@pytest.fixture
def test_pdf(tmp_path):
    """Create a simple test PDF."""
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "3.2 Test Header", fontsize=16)
    page.insert_text((72, 200), "Table | Data", fontsize=12)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def test_session(test_pdf):
    """Create a test calibration session."""
    schema = CalibrationSchema()
    session = CalibrationSession(
        key="test-cli-session",
        preset_id="test-cli",
        client="test",
        pdf_path=str(test_pdf),
        page_count=1,
        status=SessionStatus.IN_PROGRESS,
        owner="test",
    )

    # Clean up any existing session
    existing = schema.get_session("test-cli-session")
    if existing:
        schema.sessions.delete("test-cli-session")

    schema.create_session(session.to_arango())
    yield "test-cli-session"

    # Cleanup
    try:
        schema.sessions.delete("test-cli-session")
    except Exception:
        pass


class TestDetectCommand:
    """Tests for calibrate detect command."""

    def test_detect_returns_elements(self, test_pdf):
        """Test detect returns elements for a page."""
        elements_by_page = detect_elements(str(test_pdf), page_numbers=[0])
        assert 0 in elements_by_page
        assert len(elements_by_page[0]) >= 1

    def test_detect_finds_header(self, test_pdf):
        """Test detect finds header element."""
        elements_by_page = detect_elements(str(test_pdf), page_numbers=[0])
        elements = elements_by_page[0]

        header_elements = [e for e in elements if e.element_type == "header"]
        assert len(header_elements) >= 1
        assert "Test Header" in header_elements[0].text


class TestStatusCommand:
    """Tests for calibrate status command."""

    def test_status_returns_stats(self, test_session):
        """Test status returns session stats."""
        schema = CalibrationSchema()
        handler = FeedbackHandler(schema)

        stats = handler.get_session_stats(test_session)
        assert "reviewed" in stats
        assert "accuracy" in stats
        assert "by_type" in stats
        assert stats["reviewed"] == 0
        assert stats["accuracy"] == 0.0


class TestFinishCommand:
    """Tests for calibrate finish command."""

    def test_finish_requires_min_examples(self, test_session):
        """Test finish fails without minimum examples."""
        schema = CalibrationSchema()
        handler = FeedbackHandler(schema)
        stats = handler.get_session_stats(test_session)

        # Flight check should fail with 0 examples
        checks = {
            "min_examples": stats["reviewed"] >= 20,
            "accuracy_threshold": stats["accuracy"] >= 90.0,
        }

        assert not checks["min_examples"]
        assert not all(checks.values())


class TestSessionResume:
    """Tests for session auto-resume."""

    def test_find_session_by_pdf(self, test_session, test_pdf):
        """Test find_session_by_pdf returns existing session."""
        schema = CalibrationSchema()
        found = schema.find_session_by_pdf(str(test_pdf))

        assert found is not None
        assert found["_key"] == test_session

    def test_find_session_by_pdf_not_found(self):
        """Test find_session_by_pdf returns None for unknown PDF."""
        schema = CalibrationSchema()
        found = schema.find_session_by_pdf("/nonexistent/path.pdf")

        assert found is None


class TestElementPresentation:
    """Tests for element presentation format (Task 5)."""

    def test_detect_output_includes_all_presentation_fields(self, test_pdf):
        """Test detect output includes all fields needed for presentation."""
        elements_by_page = detect_elements(str(test_pdf), page_numbers=[0])

        # Should have at least one element
        assert 0 in elements_by_page
        elements = elements_by_page[0]
        assert len(elements) >= 1

        # Check element has all required presentation fields
        elem = elements[0]
        assert hasattr(elem, "element_idx"), "Missing element_idx"
        assert hasattr(elem, "element_type"), "Missing element_type"
        assert hasattr(elem, "bbox"), "Missing bbox"
        assert hasattr(elem, "confidence"), "Missing confidence"
        assert hasattr(elem, "reasoning"), "Missing reasoning"
        assert hasattr(elem, "page_num"), "Missing page_num"

        # Verify field values are reasonable
        assert elem.element_idx >= 0
        assert elem.element_type in ["header", "table", "figure"]
        assert len(elem.bbox) == 4
        assert 0.0 <= elem.confidence <= 1.0
        assert elem.reasoning != ""  # Should have some reasoning

    def test_header_element_has_font_info(self, test_pdf):
        """Test header elements include font info for presentation."""
        elements_by_page = detect_elements(str(test_pdf), page_numbers=[0])
        elements = elements_by_page[0]

        headers = [e for e in elements if e.element_type == "header"]
        assert len(headers) >= 1

        header = headers[0]
        assert header.font_info is not None, "Header should have font_info"
        assert header.font_info.size > 0, "Font size should be positive"
        assert header.font_info.name != "", "Font name should not be empty"
