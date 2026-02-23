#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["PyMuPDF>=1.24.9"]
# ///

"""
Fail if the annotated PDF has zero annotations on the first N pages.

Usage:
  uv run scripts/smokes/smoke_annotated_has_annots.py \
    --pdf scripts/artifacts/BHT_CV32A65X_with_requirements_annotated.pdf --pages 3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def has_annots(page) -> bool:
    try:
        if page.first_annot is not None:
            return True
    except Exception:
        pass
    try:
        ann = page.annots()
        if ann:
            # iter-like; check one element
            for _ in ann:
                return True
    except Exception:
        pass
    return False


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Check there are annotations on first N pages.")
    ap.add_argument("--pdf", type=Path, required=True)
    ap.add_argument("--pages", type=int, default=3)
    args = ap.parse_args(argv)

    import fitz  # PyMuPDF

    doc = fitz.open(str(args.pdf))
    n = min(args.pages, len(doc))
    missing = []
    for i in range(n):
        if not has_annots(doc[i]):
            missing.append(i + 1)
    if missing:
        print(f"Missing annotations on pages: {missing}", file=sys.stderr)
        return 1
    print(f"OK: annotations present on pages 1..{n} in {args.pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
