#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Debug harness for Stage 04 (Sections)."""

from __future__ import annotations

import argparse
from pathlib import Path

from extractor.pipeline.steps import _04_section_builder as stage04


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", type=Path, required=True, help="02_marker_blocks.json")
    ap.add_argument("--pdfdir", type=Path, required=True, help="dir with *_clean.pdf")
    ap.add_argument("--out", type=Path, required=True, help="pipeline results root")
    args = ap.parse_args()

    stage04.run(args.blocks, args.pdfdir, args.out)
    print("stage04:done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
