#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from shutil import copy2

# Load expected_common directly by path for script execution
import importlib.util as _ilu
import sys as _sys

_ec_path = Path("scripts/tools/expected_common.py")
spec = _ilu.spec_from_file_location("expected_common", _ec_path)
if spec and spec.loader:
    _mod = _ilu.module_from_spec(spec)
    _sys.modules["expected_common"] = _mod
    spec.loader.exec_module(_mod)
    STEP_FILES = _mod.STEP_FILES
else:
    raise RuntimeError(f"Failed to load expected_common from {_ec_path}")


def ts() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Snapshot current pipeline JSONs and visuals to timestamped dir"
    )
    ap.add_argument(
        "--out", required=True, type=Path, help="pipeline results root (data/results/pipeline)"
    )
    ap.add_argument("--visual-dir", type=Path, default=Path("scripts/artifacts/visuals"))
    ap.add_argument("--dest-root", type=Path, default=Path("scripts/artifacts/snapshots"))
    ap.add_argument("--steps", default="01,02,04,05,06,07,09")
    args = ap.parse_args()

    dest = args.dest_root / ts()
    dest.mkdir(parents=True, exist_ok=True)

    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    manifest = {"json": [], "visual": []}

    # Copy JSONs
    for step in steps:
        for rel in STEP_FILES.get(step, []):
            src = args.out / rel
            if not src.exists():
                continue
            dst = dest / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            copy2(src, dst)
            manifest["json"].append(str(dst))

    # Copy visuals if present
    if args.visual_dir.exists():
        for step in steps:
            vsrc = args.visual_dir / step
            if not vsrc.exists():
                continue
            vdst = dest / "visual" / step
            vdst.mkdir(parents=True, exist_ok=True)
            for img in sorted(vsrc.glob("*.png")):
                copy2(img, vdst / img.name)
                manifest["visual"].append(str(vdst / img.name))

    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"snapshot: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
