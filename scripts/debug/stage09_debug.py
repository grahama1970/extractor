#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Debug harness for Stage 09 (Section Summarizer)."""
from __future__ import annotations

import argparse
from pathlib import Path

from extractor.pipeline.steps import _09_section_summarizer as stage09


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input", type=Path, required=True, help="07_reflowed.json or 08_theorems.json"
    )
    ap.add_argument("--out", type=Path, required=True, help="Results root (pipeline)")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--window", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--no-strict", action="store_true")
    args = ap.parse_args()

    stage09._cmd_run(
        input_json=args.input,
        output_dir=args.out,
        max_concurrent=int(args.concurrency),
        window_size=int(args.window),
        strict_json=not bool(args.no_strict),
        request_timeout=int(args.timeout),
    )
    print("stage09:done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
