#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
from pathlib import Path

try:
    import fitz  # PyMuPDF
except Exception as e:
    raise SystemExit("PyMuPDF not installed. pip install pymupdf\n" + str(e))


def annotate(pdf: Path, boxes_json: Path, out_pdf: Path):
    boxes = json.loads(boxes_json.read_text(encoding="utf-8")) if boxes_json.exists() else []
    doc = fitz.open(pdf)
    for b in boxes:
        try:
            page_index = int(b.get("page", 1)) - 1
            x = float(b["x"]); y = float(b["y"]); w = float(b["w"]); h = float(b["h"])  # normalized
            pid = str(b.get("id", ""))
        except Exception:
            continue
        if page_index < 0 or page_index >= len(doc):
            continue
        page = doc[page_index]
        r = page.rect
        rect = fitz.Rect(x * r.width, y * r.height, (x + w) * r.width, (y + h) * r.height)
        page.draw_rect(rect, color=(1, 0, 0), width=1.2)
        if pid:
            page.insert_text(fitz.Point(rect.x0, max(0, rect.y0 - 8)), pid, fontsize=8, color=(1, 0, 0))
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_pdf)
    doc.close()


def main():
    ap = argparse.ArgumentParser(description="Annotate a PDF with rectangles from a boxes JSON")
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--boxes", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    annotate(Path(args.pdf), Path(args.boxes), Path(args.out))


if __name__ == "__main__":
    main()

