import os
import tempfile
from pathlib import Path
import pytest

fitz = None
try:
    import fitz  # type: ignore
except Exception:
    pass

pytestmark = pytest.mark.skipif(fitz is None, reason="PyMuPDF not installed")


def _make_pdf(tmpdir: Path) -> Path:
    """Generate a PDF file with 'Hello, world!' text."""
    p = tmpdir / "hello.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello, world!")
    doc.save(os.fspath(p))
    doc.close()
    return p


def test_extract_fast_text_basic():
    """Extract text from a PDF file using fast extraction methods."""
    from extractor.fast_extract.pymupdf_fast import extract_fast_text

    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        pdf = _make_pdf(tmpdir)
        data = extract_fast_text(os.fspath(pdf))
        assert data["source"].endswith("hello.pdf")
        assert "pages" in data and isinstance(data["pages"], list) and len(data["pages"]) >= 1
        assert "page_count" in data
        assert any("Hello" in (p.get("text") or "") for p in data["pages"])


def test_extract_fast_text_pages_slice():
    """Extract text from specified pages of a PDF document."""
    from extractor.fast_extract.pymupdf_fast import extract_fast_text

    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        pdf = _make_pdf(tmpdir)
        data = extract_fast_text(os.fspath(pdf), pages=[1])  # 1-based
        assert data["page_count"] == 1
        assert len(data["pages"]) == 1
