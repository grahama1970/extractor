#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "Pillow>=10.3.0",
# ]
# ///

from __future__ import annotations

import argparse
from pathlib import Path
from PIL import Image, ImageChops

# Map short step to directory name for per-step/visual locations
STEP_DIR = {
    "02": "02_marker_extractor",
    "05": "05_table_extractor",
    "06": "06_figure_extractor",
}


def _diff(a: Path, b: Path, *, threshold: int = 10) -> tuple[bool, int]:
    ia = Image.open(a).convert("RGB")
    ib = Image.open(b).convert("RGB")
    if ia.size != ib.size:
        return False, -1
    d = ImageChops.difference(ia, ib)
    # binarize differences above threshold
    bands = d.split()
    count = 0
    for band in bands:
        count += sum(1 for px in band.getdata() if px > threshold)
    ok = count == 0
    return ok, count


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare two visual directories per-step")
    ap.add_argument("--expected", required=True, type=Path)
    ap.add_argument("--actual", required=True, type=Path)
    ap.add_argument("--steps", default="02,05,06")
    ap.add_argument("--threshold", type=int, default=10)
    args = ap.parse_args()

    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    failures = 0
    for s in steps:
        step_dir = STEP_DIR.get(s, s)
        exp_dir = args.expected / step_dir / "visual"
        act_dir = args.actual / step_dir / "visual"
        if not exp_dir.exists() or not act_dir.exists():
            print(f"WARN: missing visual dir for step {s}")
            continue
        for img in sorted(exp_dir.glob("*.png")):
            other = act_dir / img.name
            if not other.exists():
                print(f"{s}: missing actual image {other}")
                failures += 1
                continue
            ok, count = _diff(img, other, threshold=args.threshold)
            if not ok:
                print(f"{s}: DIFF {img.name} (pixels>{args.threshold}: {count})")
                failures += 1

    if failures:
        print(f"FAILED: {failures} visual mismatch(es)")
        return 2
    print("Visuals match expected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
