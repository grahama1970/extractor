#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "loguru>=0.7.0",
#   "python-dotenv>=1.0.0",
# ]
# ///

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from loguru import logger

from .expected_common import STEP_FILES, normalized_json


def main() -> int:
    p = argparse.ArgumentParser(description="Verify pipeline outputs against expected goldens")
    p.add_argument("--pdf", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--expected-root", required=True, type=Path)
    p.add_argument("--steps", default="01,02,04,05,06,07,09")
    args = p.parse_args()

    try:
        load_dotenv(find_dotenv(), override=True)
    except Exception:
        pass

    base = args.pdf.stem
    expected_root = args.expected_root / base
    steps = [s.strip() for s in args.steps.split(",") if s.strip()]

    logger.remove()
    logger.add(lambda msg: print(msg, end=""), level="INFO", format="{message}")

    failures = 0
    for step in steps:
        for rel in STEP_FILES.get(step, []):
            got = args.out / rel
            exp = expected_root / rel
            if not got.exists():
                logger.error(f"{step}: missing output {got}\n")
                failures += 1
                continue
            if not exp.exists():
                logger.error(f"{step}: missing expected {exp}\n")
                failures += 1
                continue
            got_n = normalized_json(got)
            exp_n = normalized_json(exp)
            if got_n != exp_n:
                logger.error(f"{step}: DIFF → {rel}\n  expected: {exp}\n  got:      {got}\n")
                failures += 1
            else:
                logger.info(f"{step}: ok → {rel}\n")

    if failures:
        logger.error(f"FAILED: {failures} mismatch(es).\n")
        return 2
    logger.info("All selected steps match expected.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
