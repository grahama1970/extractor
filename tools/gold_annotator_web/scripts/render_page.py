#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path

try:
    import fitz  # PyMuPDF
except Exception as e:
    raise SystemExit("PyMuPDF not installed. pip install pymupdf\n"+str(e))


def render_page(pdf: Path, page_num: int, out_path: Path, dpi: int = 96):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf)
    try:
        if page_num < 1 or page_num > len(doc):
            raise SystemExit(f"page out of range: {page_num}")
        mat = fitz.Matrix(dpi/72.0, dpi/72.0)
        page = doc[page_num-1]
        pix = page.get_pixmap(matrix=mat, alpha=False)
        out_path.write_bytes(pix.tobytes("png"))
    finally:
        doc.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--page", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dpi", type=int, default=96)
    args = ap.parse_args()
    render_page(Path(args.pdf), args.page, Path(args.out), dpi=args.dpi)


if __name__ == "__main__":
    main()

