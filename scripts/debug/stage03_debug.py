#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Debug harness for Stage 03 (Suspicious Headers)."""
from __future__ import annotations

import argparse
from pathlib import Path

from extractor.pipeline.steps import _03_suspicious_headers as stage03


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", type=Path, required=True, help="Bundle with marker_blocks + clean_pdf")
    ap.add_argument("--out", type=Path, required=True, help="Results root (pipeline)")
    args = ap.parse_args()

    stage03.debug_bundle(args.bundle, args.out)
    print("stage03:done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

