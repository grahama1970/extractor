#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Minimal debug harness for Stage 05 (Tables)."""

from __future__ import annotations

import argparse
from pathlib import Path

from extractor.pipeline.steps import _05_table_extractor as stage05


def main() -> int:
    """Run the main application pipeline."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--sections", type=Path, required=False, help="04_sections.json")
    ap.add_argument("--pdfdir", type=Path, required=False, help="dir containing *_clean.pdf")
    ap.add_argument("--out", type=Path, required=True, help="pipeline results root")
    ap.add_argument("--bundle", type=Path, required=False, help="bundle with {sections, clean_pdf}")
    args = ap.parse_args()

    if args.bundle:
        stage05.debug_bundle(args.bundle, args.out)
    else:
        if not (args.sections and args.pdfdir):
            raise SystemExit("provide --bundle or (--sections and --pdfdir)")
        stage05.run(args.sections, args.pdfdir, args.out)
    print("stage05:done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
