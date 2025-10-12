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
from typing import Dict, Any, List, Optional


def extract_fast_text(pdf_path: str, pages: Optional[List[int]] = None) -> Dict[str, Any]:
    try:
        import fitz  # PyMuPDF
    except Exception as e:
        raise RuntimeError(
            f"PyMuPDF not available: {e}. Install with: pip install pymupdf"
        )

    p = Path(pdf_path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    result_pages: List[Dict[str, Any]] = []
    with fitz.open(pdf_path) as doc:
        page_count = doc.page_count
        if pages:
            # 1-based input; clamp to valid range and unique-sort
            indices = sorted({max(1, min(page_count, n)) - 1 for n in pages if isinstance(n, int)})
        else:
            indices = range(page_count)
        for i in indices:
            page = doc.load_page(i)
            text = page.get_text("text") or ""
            result_pages.append({"page": i + 1, "text": text})

    return {
        "source": str(p.resolve()),
        "page_count": len(result_pages) if pages else page_count,
        "pages": result_pages,
    }

