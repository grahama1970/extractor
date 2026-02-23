#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path

try:
    import fitz  # PyMuPDF
except Exception as e:
    raise SystemExit("PyMuPDF not installed. pip install pymupdf\n" + str(e))


def render(pdf: Path, out_dir: Path, dpi: int = 300):
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf)
    mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    for i in range(len(doc)):
        page = doc[i]
        pix = page.get_pixmap(matrix=mat, alpha=False)
        (out_dir / f"page_{i+1:03d}.png").write_bytes(pix.tobytes("png"))
    doc.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args()
    render(Path(args.pdf), Path(args.out), dpi=args.dpi)


if __name__ == "__main__":
    main()
