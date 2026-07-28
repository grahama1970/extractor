#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Smoke: Print first N detected section headers with absolute spans.

Usage:
  uv run scripts/smokes/smoke_header_spans.py \
    --json data/results/pipeline/03_suspicious_headers/json_output/03_verified_blocks.json \
    --limit 10

Inputs:
  --json: Path to a Stage 03 or 04 JSON containing either top-level 'blocks',
          or pages[i].blocks[].
  --limit: Max headers to print (default 10).

Env:
  SPARTA_PDF_FONT_LARGE can influence bold/size heuristics when filter is used.

Output:
  TSV lines: page\tblock_index\theadline\tnum_span_start\tnum_span_end\ttitle_span_start\ttitle_span_end
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, List, Dict

from extractor.pipeline.utils.section_builder_utils import (
    find_header_candidates_in_text,
    filter_header_candidate,
)


def _load_blocks(p: Path) -> List[Dict[str, Any]]:
    """Load and extract blocks from a JSON file at the specified path."""
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if "pages" in data:
        blocks = [b for pg in data["pages"] for b in pg.get("blocks", [])]
    else:
        blocks = data.get("blocks", [])
    return blocks


def main() -> int:
    """Parse command-line arguments and process JSON data."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True, help="Path to Stage 03/04 JSON")
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    src = Path(args.json)
    if not src.exists():
        print(f"ERR: JSON not found: {src}")
        return 2

    blocks = _load_blocks(src)
    out_count = 0
    for bi, b in enumerate(blocks):
        t = (b.get("text") or b.get("content") or "").strip()
        if not t:
            continue
        cands = find_header_candidates_in_text(t)
        if not cands:
            continue
        # Filter each candidate line once; print accepted
        for c in cands:
            line = c.get("raw_line", "")
            res = filter_header_candidate(line, b.get("first_span_font") or {})
            if not res.get("is_header"):
                continue
            ns, ne = (None, None)
            ts, te = (None, None)
            spans = res.get("spans") or {}
            if spans.get("number"):
                ns = spans["number"].get("start")
                ne = spans["number"].get("end")
            if spans.get("title"):
                ts = spans["title"].get("start")
                te = spans["title"].get("end")
            page = b.get("page", b.get("page_idx", ""))
            print(f"{page}\t{bi}\t{res.get('title') or line}\t{ns}\t{ne}\t{ts}\t{te}")
            out_count += 1
            if out_count >= args.limit:
                return 0
    if out_count == 0:
        print("No headers detected in candidate pool.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
