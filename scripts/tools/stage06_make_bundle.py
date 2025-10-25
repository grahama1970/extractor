#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///

import json
import sys
from pathlib import Path
from typing import Optional


def find_latest_run(root: Path) -> Optional[Path]:
    candidates = []
    for base in [
        root / "pipeline_seq",
        root / "pipeline_xtrace",
        root / "pipeline",
    ]:
        if base.exists():
            candidates.append(base)
    if not candidates:
        return None
    # Prefer pipeline_seq, then pipeline_xtrace, then pipeline
    for c in candidates:
        return c
    return None


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Build a Stage06 debug bundle from prior stage outputs.")
    ap.add_argument("--root", default="data/results", help="Results root (default: data/results)")
    ap.add_argument("--out", default="scripts/artifacts/stage06_bundle.json", help="Output bundle path")
    args = ap.parse_args()

    root = Path(args.root)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    run_dir = find_latest_run(root)
    if run_dir is None:
        print(f"error: no results under {root}", file=sys.stderr)
        return 2

    stage02 = run_dir / "02_marker_extractor/json_output/02_marker_blocks.json"
    stage04 = run_dir / "04_section_builder/json_output/04_sections.json"
    pdf_dir = run_dir / "01_annotation_processor"
    try:
        clean_pdf = next(pdf_dir.glob("*_clean.pdf"))
    except StopIteration:
        print(f"error: no *_clean.pdf in {pdf_dir}", file=sys.stderr)
        return 3

    if not stage02.exists() or not stage04.exists():
        print(f"error: missing prior stage outputs under {run_dir}", file=sys.stderr)
        return 4

    marker_blocks = json.loads(stage02.read_text())
    sections_obj = json.loads(stage04.read_text()).get("sections", [])

    bundle = {
        "marker_blocks": marker_blocks,
        "sections": sections_obj,
        "clean_pdf": str(clean_pdf),
    }
    out.write_text(json.dumps(bundle, indent=2))
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

