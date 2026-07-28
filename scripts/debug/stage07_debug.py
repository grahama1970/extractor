#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Debug harness for Stage 07 (Reflow)."""

from __future__ import annotations

import argparse
from pathlib import Path

from extractor.pipeline.steps import _07_reflow_section as stage07


def main() -> int:
    """Parse arguments and execute stage 07."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--sections", type=Path, required=True)
    ap.add_argument("--tables", type=Path, required=True)
    ap.add_argument("--figures", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--no-images", action="store_true")
    args = ap.parse_args()

    stage07.run(
        sections=args.sections,
        tables=args.tables,
        figures=args.figures,
        output_dir=args.out,
        include_images=not bool(args.no_images),
    )
    print("stage07:done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
