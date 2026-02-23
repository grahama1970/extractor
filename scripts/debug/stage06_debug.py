#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Minimal debug harness for Stage 06 (no Typer, no pipeline).

Examples:
  # Using an auto-discovered bundle first
  python scripts/tools/stage06_make_bundle.py --root data/results --out scripts/artifacts/stage06_bundle.json

  # Offline (no network):
  python scripts/debug/stage06_debug.py --bundle scripts/artifacts/stage06_bundle.json --out data/results/pipeline --skip

  # Live:
  STAGE06_CONCURRENCY=1 python scripts/debug/stage06_debug.py --bundle scripts/artifacts/stage06_bundle.json --out data/results/pipeline
"""

from __future__ import annotations

import argparse
from pathlib import Path

from extractor.pipeline.steps import _06_figure_extractor as stage06


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", type=Path, help="Stage06 bundle JSON")
    ap.add_argument("--stage02", type=Path, help="02_marker_blocks.json")
    ap.add_argument("--sections", type=Path, help="04_sections.json")
    ap.add_argument("--pdfdir", type=Path, help="*_clean.pdf directory")
    ap.add_argument("--out", type=Path, required=True, help="Output parent dir (pipeline root)")
    ap.add_argument("--skip", action="store_true", help="Skip LLM (offline)")
    args = ap.parse_args()

    out = stage06.run(
        stage_02_json=args.stage02,
        stage_04_json=args.sections,
        pdf_dir=args.pdfdir,
        output_dir=args.out,
        bundle=args.bundle,
        skip_descriptions=bool(args.skip),
    )
    print(f"wrote → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
