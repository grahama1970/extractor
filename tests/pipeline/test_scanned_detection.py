"""Scanned PDF detection tests — requires PyMuPDF (regression only)."""
import pytest

try:
    import fitz
    from extractor.pipeline.steps.s02_pymupdf_extractor import _detect_scanned_pdf
    _HAS_FITZ = True
except (ImportError, ModuleNotFoundError):
    _HAS_FITZ = False

pytestmark = pytest.mark.skipif(not _HAS_FITZ, reason="PyMuPDF not installed (regression extra only)")


def _make_image_only_pdf(path):
    """Create an image-only PDF document at the specified path."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    pix = fitz.Pixmap(fitz.csRGB, fitz.Rect(0, 0, 612, 792))
    page.insert_image(page.rect, pixmap=pix)
    doc.save(path)
    doc.close()


def test_detect_scanned_empty_document(tmp_path):
    """Detect if a PDF document is scanned and empty."""
    doc = fitz.open()
    result = _detect_scanned_pdf(doc)
    doc.close()
    assert result["is_scanned"] is False
    assert result["reason"] == "empty_document"


def test_detect_scanned_image_only(tmp_path):
    """Verify detection of scanned image-only PDF."""
    pdf_path = tmp_path / "scanned.pdf"
    _make_image_only_pdf(str(pdf_path))

    with fitz.open(str(pdf_path)) as doc:
        result = _detect_scanned_pdf(doc)

    assert result["is_scanned"] is True
    assert result["pages_sampled"] >= 1
