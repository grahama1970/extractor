#!/usr/bin/env python3
from __future__ import annotations
import shutil
from pathlib import Path
import sys


def collect(results_root: Path, dest_root: Path) -> None:
    dest_root.mkdir(parents=True, exist_ok=True)
    for stage_dir in results_root.iterdir():
        if not stage_dir.is_dir():
            continue
        if not stage_dir.name[:2].isdigit():
            continue
        target = dest_root / stage_dir.name
        img = stage_dir / "visual_output"
        txt = stage_dir / "text_output"
        json_dir = stage_dir / "json_output"
        if img.exists():
            shutil.copytree(img, target / "images", dirs_exist_ok=True)
        if txt.exists():
            shutil.copytree(txt, target / "text", dirs_exist_ok=True)
        if json_dir.exists():
            for p in json_dir.glob("*.json"):
                target.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, target / p.name)


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "data/results/pipeline")
    dest = Path(sys.argv[2] if len(sys.argv) > 2 else "scripts/artifacts/pipeline")
    collect(out, dest)
    print(f"Collected proofs from {out} → {dest}")

