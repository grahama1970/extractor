#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv>=1.0.0",
# ]
# ///

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from .expected_common import STEP_FILES


def main() -> int:
    p = argparse.ArgumentParser(description="Bless current pipeline outputs as expected (golden)")
    p.add_argument("--pdf", required=True, type=Path)
    p.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Path used for current outputs (data/results/pipeline)",
    )
    p.add_argument(
        "--expected-root",
        required=True,
        type=Path,
        help="Root expected dir (data/expected/pipeline)",
    )
    p.add_argument("--steps", default="01,02,04,05,06,07,09")
    p.add_argument(
        "--visual-dir",
        type=Path,
        help="Optional: copy rendered visuals from here (expects subdirs per step)",
    )
    args = p.parse_args()

    try:
        load_dotenv(find_dotenv(), override=True)
    except Exception:
        pass

    base = args.pdf.stem
    target_root = args.expected_root / base
    target_root.mkdir(parents=True, exist_ok=True)

    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    copied = 0
    for step in steps:
        for rel in STEP_FILES.get(step, []):
            src = args.out / rel
            dst = target_root / rel
            if not src.exists():
                print(f"WARN: missing output for step {step}: {src}")
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"blessed: {dst}")
            copied += 1

    # Optional: bless visuals
    if args.visual_dir and args.visual_dir.exists():
        for step in steps:
            src_dir = args.visual_dir / step
            if not src_dir.exists():
                continue
            dst_dir = target_root / "visual" / step
            dst_dir.mkdir(parents=True, exist_ok=True)
            for img in sorted(src_dir.glob("*.png")):
                shutil.copy2(img, dst_dir / img.name)
                print(f"blessed visual: {dst_dir / img.name}")

    print(f"done. {copied} files blessed under {target_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
