import fitz
from extractor.pipeline.tools import render_annotated_pdf as rap


def test_rect_from_camelot_converts_properly():
    page_rect = fitz.Rect(0, 0, 600, 800)
    camelot_bb = [50, 100, 300, 200]  # x0,y0,x1,y1 with origin bottom-left
    r = rap._rect_from_camelot(camelot_bb, page_rect)
    assert r is not None
    # y flipped: y0' = 800-200=600, y1' = 800-100=700
    assert (int(r.x0), int(r.y0), int(r.x1), int(r.y1)) == (50, 600, 300, 700)


def test_parse_pages_various_patterns():
    total = 20
    # 1,3,10-12 -> {0,2,9,10,11}
    s = rap._parse_pages("1,3,10-12", total)
    assert s == {0, 2, 9, 10, 11}
    # empty / invalid
    assert rap._parse_pages("", total) is None
    assert rap._parse_pages("x-y, a", total) is None

