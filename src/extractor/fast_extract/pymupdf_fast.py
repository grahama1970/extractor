"""
Fast PDF text extraction using PyMuPDF only (no marker/surya imports).

Returns a very simple JSON structure:
{
  "source": "path.pdf",
  "pages": [
    {"page": 1, "text": "..."},
    ...
  ]
}
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List


def extract_fast_text(pdf_path: str) -> Dict[str, Any]:
    try:
        import fitz  # PyMuPDF
    except Exception as e:
        raise RuntimeError(
            f"PyMuPDF not available: {e}. Install with: pip install pymupdf"
        )

    p = Path(pdf_path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    pages: List[Dict[str, Any]] = []
    for i in range(doc.page_count):
        page = doc.load_page(i)
        text = page.get_text("text") or ""
        pages.append({"page": i + 1, "text": text})
    doc.close()

    return {"source": str(p), "pages": pages}

