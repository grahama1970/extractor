#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Build a minimal Stage 06 debug bundle (no network required).

The bundle JSON contains:
  - marker_blocks: contents of Stage 02 02_marker_blocks.json
  - sections:     sections list from Stage 04 04_sections.json
  - clean_pdf:    path to the *_clean.pdf from Stage 01

Usage examples:
  python scripts/tools/stage06_make_bundle.py \
    --stage02 data/results/pipeline/02_marker_extractor/json_output/02_marker_blocks.json \
    --sections data/results/pipeline/04_section_builder/json_output/04_sections.json \
    --pdf data/results/pipeline/01_annotation_processor/BHT_CV32A65X_with_requirements_clean.pdf \
    --out scripts/artifacts/stage06_bundle.json

  # Auto-discover under a root (best effort):
  python scripts/tools/stage06_make_bundle.py --root data/results --out scripts/artifacts/stage06_bundle.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def find_one(glob_str: str) -> Path | None:
    candidates = sorted(Path(".").glob(glob_str))
    return candidates[-1] if candidates else None


def autodiscover(root: Path) -> tuple[Path | None, Path | None, Path | None]:
    """Best-effort discovery under a pipeline results root."""
    s02 = find_one(str(root / "**/02_marker_extractor/json_output/02_marker_blocks.json"))
    s04 = find_one(str(root / "**/04_section_builder/json_output/04_sections.json"))
    pdf = None
    # Prefer Stage 01 dir near discovered Stage 02
    if s02:
        p01 = s02.parents[4] / "01_annotation_processor"
        pdf = find_one(str(p01 / "*_clean.pdf"))
    if not pdf:
        pdf = find_one(str(root / "**/01_annotation_processor/*_clean.pdf"))
    return s02, s04, pdf


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage02", type=Path, help="02_marker_blocks.json")
    ap.add_argument("--sections", type=Path, help="04_sections.json")
    ap.add_argument("--pdf", type=Path, help="*_clean.pdf path")
    ap.add_argument("--root", type=Path, help="Auto-discover root (e.g., data/results)")
    ap.add_argument("--out", type=Path, required=True, help="Output bundle path")
    args = ap.parse_args()

    s02 = args.stage02
    s04 = args.sections
    pdf = args.pdf

    if (not s02 or not s04 or not pdf) and args.root:
        s02, s04, pdf = autodiscover(args.root)

    if not (s02 and s04 and pdf):
        print("error: provide --stage02, --sections, --pdf or a --root to auto-discover")
        return 2

    stage02_data = json.loads(Path(s02).read_text())
    sections_data = json.loads(Path(s04).read_text())

    bundle = {
        "marker_blocks": stage02_data,
        "sections": sections_data.get("sections", []),
        "clean_pdf": str(Path(pdf).resolve()),
    }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(bundle, indent=2))
    print(f"wrote bundle → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

