#!/usr/bin/env python3
"""
Stage 05 keep-all smoke (offline)

Usage:
  python scripts/smokes/pipeline/offline/smoke_stage05_keep_all.py \
    --tables data/results/pipeline/05_table_extractor/json_output/05_tables.json \
    --page 3 --min 2

Checks that for the specified 0-based page index, the number of tables
in 05_tables.json is at least --min (default 2).
Exits 0 on success, 1 on failure, 2 on input errors.
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List


def main() -> int:
    """Validate page table count against a minimum threshold."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", required=True, help="Path to 05_tables.json")
    ap.add_argument("--page", type=int, required=True, help="0-based page index to check")
    ap.add_argument(
        "--min", dest="min_count", type=int, default=2, help="Minimum tables expected on the page"
    )
    args = ap.parse_args()

    p = Path(args.tables)
    if not p.exists():
        print(f"tables file not found: {p}", file=sys.stderr)
        return 2
    try:
        data: Dict[str, Any] = json.loads(p.read_text())
    except Exception as e:
        print(f"failed to parse JSON: {e}", file=sys.stderr)
        return 2

    tables: List[Dict[str, Any]] = data.get("tables") or []
    cnt = sum(1 for t in tables if int(t.get("page_index", -1)) == args.page)
    print(f"page {args.page}: tables={cnt} (min={args.min_count})")
    if cnt >= args.min_count:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
