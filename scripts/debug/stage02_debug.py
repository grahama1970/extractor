#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Debug harness for Stage 02 (Marker)."""

from __future__ import annotations

import argparse
from pathlib import Path

from extractor.pipeline.steps import _02_marker_extractor as stage02


def main() -> int:
    """Parse command-line arguments and execute the processing stage."""
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path, help="input PDF path")
    ap.add_argument("--out", type=Path, required=True, help="pipeline results root")
    ap.add_argument("--no-spawn", action="store_true")
    args = ap.parse_args()

    stage02.run(args.pdf, args.out, no_spawn=bool(args.no_spawn))
    print("stage02:done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
