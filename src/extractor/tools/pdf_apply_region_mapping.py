#!/usr/bin/env python3
"""
Apply a simple CSV mapping (id,type,page,x0,y0,x1,y1,expected_json) to a PDF by
embedding FreeText annotations with the mini-schema next to the rectangles.

If rectangle annotations already exist, this will only add the FreeText machine_note.
If a rectangle is missing, you can pass --draw-rects to draw them.

After applying, you can generate gold with:
  python -m src.extractor.tools.pdf_annotations_to_gold --pdf <out_pdf> --repo-root . --force
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import List, Dict

import fitz  # PyMuPDF


def main():
    ap = argparse.ArgumentParser(description="Embed mapping CSV into PDF as FreeText machine_notes")
    ap.add_argument("--pdf", required=True, help="Input PDF")
    ap.add_argument(
        "--mapping",
        required=True,
        help="CSV file with columns id,type,page,x0,y0,x1,y1,expected_json",
    )
    ap.add_argument("--out", required=True, help="Output PDF path")
    ap.add_argument("--draw-rects", action="store_true", help="Draw rectangles as well if missing")
    args = ap.parse_args()

    rows: List[Dict[str, str]] = []
    with open(args.mapping, newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            rows.append(r)

    doc = fitz.open(args.pdf)
    for r in rows:
        page_idx = max(0, int(r.get("page", 1)) - 1)
        x0 = float(r["x0"])
        y0 = float(r["y0"])
        x1 = float(r["x1"])
        y1 = float(r["y1"])
        rect = fitz.Rect(x0, y0, x1, y1)
        page = doc[page_idx]
        if args.draw - rects:
            try:
                page.add_rect_annot(rect)
            except AttributeError:
                page.addRectAnnot(rect)

        meta = {
            k: v
            for k, v in {
                "id": (r.get("id") or "").strip(),
                "type": (r.get("type") or "").strip(),
                "expected_json": (r.get("expected_json") or "").strip(),
            }.items()
            if v
        }
        if not meta:
            continue
        content = json.dumps(meta, ensure_ascii=False)
        try:
            page.add_freetext_annot(rect, content)
        except AttributeError:
            page.addFreetextAnnot(rect, content)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out)
    doc.close()
    print(f"Wrote annotated PDF: {out}")
    print(
        "Next: python -m src.extractor.tools.pdf_annotations_to_gold --pdf {out} --repo-root . --force"
    )


if __name__ == "__main__":  # pragma: no cover
    main()
