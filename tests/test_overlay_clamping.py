import json
from pathlib import Path

import fitz  # PyMuPDF

from extractor.pipeline.tools import render_annotated_pdf as rpdf


def _make_blank_pdf(tmp_path: Path, w: float = 600, h: float = 800) -> Path:
    out = tmp_path / "blank.pdf"
    doc = fitz.open()
    try:
        page = doc.new_page(width=w, height=h)
        page.insert_text((72, 72), "Test Page", fontsize=12)
        doc.save(out)
    finally:
        doc.close()
    return out


def test_clamp_to_page_negative_height_returns_none():
    page_rect = fitz.Rect(0, 0, 600, 800)
    bad = fitz.Rect(10, -20, 100, -5)  # entirely above page; negative height
    assert rpdf._clamp_to_page(bad, page_rect) is None


def test_from_blocks_handles_out_of_bounds_and_writes_pdf(tmp_path):
    pdf_path = _make_blank_pdf(tmp_path)
    # Create blocks JSON with an out-of-bounds bbox (negative y) and one valid
    blocks = {
        "blocks": [
            {"block_type": "Text", "page": 0, "bbox": [66.18, -4.71, 126.18, -2.0]},
            {"block_type": "SectionHeader", "page": 0, "bbox": [50, 50, 120, 70]},
        ]
    }
    blocks_json = tmp_path / "02_marker_blocks.json"
    blocks_json.write_text(json.dumps(blocks))

    out_pdf = tmp_path / "annotated.pdf"
    rpdf.from_blocks(
        pdf=pdf_path,
        blocks_json=blocks_json,
        out=out_pdf,
        block_type_key="block_type",
        min_width=1.0,
        min_height=1.0,
    )
    assert out_pdf.exists() and out_pdf.stat().st_size > 0
