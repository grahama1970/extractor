#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Debug harness for Stage 12 (Insert Annotations)."""
from __future__ import annotations

import argparse
from pathlib import Path

from extractor.pipeline.steps import _12_insert_annotations as stage12


def main() -> int:
    """Process annotations with stage12, saving results to output."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotations", type=Path, required=True, help="01_annotations.json path")
    ap.add_argument("--out", type=Path, required=True, help="Results root (pipeline)")
    args = ap.parse_args()

    stage12.run(annotations=args.annotations, output_dir=args.out, mode="both")
    print("stage12:done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
