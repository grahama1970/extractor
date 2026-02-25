import fitz

from extractor.pipeline.steps.s02_pymupdf_extractor import _detect_scanned_pdf


def _make_image_only_pdf(path):
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    pix = fitz.Pixmap(fitz.csRGB, fitz.Rect(0, 0, 612, 792))
    page.insert_image(page.rect, pixmap=pix)
    doc.save(path)
    doc.close()


def test_detect_scanned_empty_document(tmp_path):
    doc = fitz.open()
    result = _detect_scanned_pdf(doc)
    doc.close()
    assert result["is_scanned"] is False
    assert result["reason"] == "empty_document"


def test_detect_scanned_image_only(tmp_path):
    pdf_path = tmp_path / "scanned.pdf"
    _make_image_only_pdf(str(pdf_path))

    with fitz.open(str(pdf_path)) as doc:
        result = _detect_scanned_pdf(doc)

    assert result["is_scanned"] is True
    assert result["pages_sampled"] >= 1
