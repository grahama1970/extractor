"""
Build a Stage 03 debug bundle by taking a Stage 02 JSON, forcing a specific
text line to be treated as a suspicious SectionHeader candidate, and writing a
bundle JSON that Stage 03's `debug-bundle` command accepts.

Usage example:

  python scripts/build_suspicious_headers_bundle.py \
    --source-json data/results/pipeline/02_marker_extractor/json_output/02_marker_blocks_hw_misclass.json \
    --clean-pdf data/input/pipeline/cleaned_BHT_CV32A65X_marked.pdf \
    --out data/results/pipeline/03_suspicious_headers/debug/suspicious_headers_bundle.json \
    --phrase "^\s*For any HW configuration"
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Build suspicious-headers debug bundle for Stage 03")
    ap.add_argument("--source-json", required=True, help="Path to Stage 02 JSON (02_marker_blocks_*.json)")
    ap.add_argument("--clean-pdf", required=True, help="Path to the clean PDF from Stage 01")
    ap.add_argument("--out", default="data/results/pipeline/03_suspicious_headers/debug/suspicious_headers_bundle.json", help="Output bundle JSON path")
    ap.add_argument("--phrase", default=r"^\s*For any HW configuration", help="Regex for the text line to promote to a header candidate")
    ap.add_argument("--add-reason", default="test_misclassification", help="Extra suspicious reason tag to add")
    args = ap.parse_args()

    src = Path(args.source_json)
    if not src.exists():
        raise SystemExit(f"Stage 02 JSON not found: {src}")
    clean_pdf = Path(args.clean_pdf)
    if not clean_pdf.exists():
        raise SystemExit(f"Clean PDF not found: {clean_pdf}")

    try:
        obj = json.loads(src.read_text())
    except Exception as e:
        raise SystemExit(f"Failed to read JSON from {src}: {e}")

    blocks = obj.get("blocks") or []
    pat = re.compile(args.phrase, flags=re.I)
    idx = -1
    for i, b in enumerate(blocks):
        t = (b.get("text") or "").strip()
        if pat.search(t):
            idx = i
            break
    if idx < 0:
        # surface nearby candidates to aid debugging
        for i, b in enumerate(blocks):
            t = (b.get("text") or "")
            if "HW configuration" in t:
                print(f"Candidate {i}: {t[:120].replace('\n',' ')}")
        raise SystemExit(f"Target phrase not found in Stage 02 JSON: {args.phrase}")

    # Promote to candidate header with suspicion flags
    b = blocks[idx]
    b["block_type"] = "SectionHeader"
    b["suspicious_header"] = True
    b["is_suspicious"] = True
    reasons = set([*(b.get("suspicious_reasons") or []), args.add_reason])
    b["suspicious_reasons"] = sorted(reasons)
    obj["blocks"] = blocks

    # Write the bundle
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bundle = {"marker_blocks": obj, "clean_pdf": os.path.abspath(str(clean_pdf))}
    out_path.write_text(json.dumps(bundle, indent=2))
    print(f"Bundle written: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

