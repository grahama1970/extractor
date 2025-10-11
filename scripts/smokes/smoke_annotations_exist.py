#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pymupdf>=1.24.9",
# ]
# ///

import argparse
from pathlib import Path
import sys

try:
    import fitz  # type: ignore
except Exception as e:
    print(f"PyMuPDF not available: {e}", file=sys.stderr)
    sys.exit(2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, help="Path to Stage 01 clean PDF (_clean.pdf)")
    ap.add_argument("--pages", type=int, default=5, help="Pages to check (from start)")
    args = ap.parse_args()

    pdf = Path(args.pdf)
    stem = pdf.stem[:-6] if pdf.stem.endswith("_clean") else pdf.stem
    out = Path("scripts/artifacts") / f"{stem}__run_annotated_prev.pdf"
    if not out.exists():
        print(f"Annotated PDF not found: {out}", file=sys.stderr)
        return 2
    doc = fitz.open(out.as_posix())
    N = min(args.pages, len(doc))
    ok = True
    for i in range(N):
        has = False
        try:
            has = doc[i].first_annot is not None
        except Exception:
            try:
                has = any(True for _ in (doc[i].annots() or []))
            except Exception:
                has = False
        if not has:
            print(f"Missing annotations on page {i+1}", file=sys.stderr)
            ok = False
    if not ok:
        return 1
    print(f"Smoke OK: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

