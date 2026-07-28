import importlib.util
import sys
from pathlib import Path

import fitz


def _load_legacy_module():
    """Dynamically load scripts/tools/pdf_annotate_from_pipeline.py as a module."""
    path = Path("scripts/tools/pdf_annotate_from_pipeline.py").resolve()
    spec = importlib.util.spec_from_file_location("legacy_annot", str(path))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def test_camelot_to_fitz_bbox_against_page_height():
    """Validate bounding box conversion against page dimensions."""
    legacy = _load_legacy_module()
    page_rect = fitz.Rect(0, 0, 600, 800)
    bb = [50, 100, 300, 200]
    conv = legacy._camelot_to_fitz_bbox(bb, page_rect)
    assert conv == [50.0, 600.0, 300.0, 700.0]


def test_put_box_fill_and_tab_creates_annotations(tmp_path):
    """Test legacy `_put_box` creates annotations with fill and tab."""
    legacy = _load_legacy_module()
    # Create a one-page blank PDF
    out = tmp_path / "onepage.pdf"
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    doc.save(out.as_posix())
    doc.close()

    # Re-open and annotate using legacy _put_box (annotation objects)
    doc = fitz.open(out.as_posix())
    page = doc[0]
    bbox = [100, 100, 300, 250]
    color = (0.1, 0.6, 0.95)
    legacy._put_box(
        page,
        bbox,
        color,
        text="very-long-label-text-to-trigger-tab",
        lw=1.0,
        fontsize=6.5,
        tag_only=False,
        use_annots=True,
        do_fill=True,
        fill_alpha=0.05,
    )
    out2 = tmp_path / "onepage_annot.pdf"
    doc.save(out2.as_posix())
    # Count annotation types
    page = fitz.open(out2.as_posix())[0]
    types = []
    a = page.first_annot
    while a:
        try:
            types.append(a.type[1])
        except Exception:
            pass
        a = a.next
    # Expect at least a Square and a FreeText annotation
    assert any(t.lower() == "square" for t in types)
    assert any(t.lower() == "freetext" for t in types)
