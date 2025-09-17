#!/usr/bin/env python3
"""
List rectangle annotations from a PDF and emit a CSV you can edit.

Output columns:
  id,type,page,x0,y0,x1,y1,expected_json

Defaults:
  - id: <doc_stem>_page{page:02d}_r{idx:02d}
  - type: (empty)
  - expected_json: suggestion under data/gold_standards/{tables|sections}/<id>.json once you set 'type'

Usage:
  python -m src.extractor.tools.pdf_list_regions --pdf data/input/pipeline/BHT_CV32A65X_marked.pdf --out mapping.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from src.extractor.tools.labelstudio.convert_pdf_annotations import (
    extract_regions_from_pdf,
)


def main():
    ap = argparse.ArgumentParser(description="List rectangle regions from PDF → CSV mapping")
    ap.add_argument("--pdf", required=True, help="Annotated PDF path")
    ap.add_argument("--out", required=True, help="Output CSV path")
    args = ap.parse_args()

    pdf = Path(args.pdf)
    if not pdf.exists():
        raise SystemExit(f"PDF not found: {pdf}")

    pages_regions, _ = extract_regions_from_pdf(pdf)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "type", "page", "x0", "y0", "x1", "y1", "expected_json"])
        for page_index, page_regions in enumerate(pages_regions, start=1):
            for reg_index, reg in enumerate(page_regions, start=1):
                rid = f"{pdf.stem}_page{page_index:02d}_r{reg_index:02d}"
                x0, y0, x1, y1 = reg.box.x0, reg.box.y0, reg.box.x1, reg.box.y1
                writer.writerow(
                    [rid, "", page_index, f"{x0:.2f}", f"{y0:.2f}", f"{x1:.2f}", f"{y1:.2f}", ""]
                )

    print(f"Wrote mapping CSV: {out_path}")
    print(
        "Edit 'type' (table|requirements|section) and 'expected_json' paths, then run pdf_apply_region_mapping.py"
    )


if __name__ == "__main__":  # pragma: no cover
    main()
