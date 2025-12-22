#!/usr/bin/env python3
"""
Stage 15: Walkthrough Generator
Generates a Markdown walkthrough with page images and overlays using scripts/generate_enhanced_walkthrough.py.

Inputs:
- Source PDF (from Stage 01 clean output or user path)
- Run results root (pipeline output dir)

Outputs:
- Markdown + images under 15_walkthrough_generator/ (see generator script)

Opt-in: enabled via --generate-walkthrough in run_pipeline.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

STEP_NAME = "15_walkthrough_generator"


def run(pdf_path: Path, run_dir: Path, output_dir: Path | None = None) -> Path | None:
    out_dir = (output_dir or run_dir) / STEP_NAME
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "scripts.generate_enhanced_walkthrough",
        str(pdf_path),
        str(out_dir),
        "--run-dir",
        str(run_dir),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"walkthrough generation failed: {proc.stderr}")
    return out_dir


def sanity() -> int:
    return 0


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, type=Path)
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    out = run(args.pdf, args.run, args.out)
    print(out)
