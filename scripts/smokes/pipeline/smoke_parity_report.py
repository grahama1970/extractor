#!/usr/bin/env python3
"""Report-only parity helper: prints block counts for supplied flattened files.

Usage:
  python scripts/smokes/pipeline/smoke_parity_report.py --refs canonical.json --candidates a.json b.json

This does not fail; it is informational for non-parity formats (pptx/xlsx, etc.).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(p: Path):
    return json.loads(p.read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refs", type=Path, required=True, nargs="+", help="Reference flattened json(s)")
    ap.add_argument("--candidates", type=Path, required=True, nargs="+", help="Candidate flattened json(s)")
    args = ap.parse_args()

    ref_counts = {p: len(load(p)) for p in args.refs}
    print("Reference counts:")
    for p, n in ref_counts.items():
        print(f"  {p}: {n}")

    print("Candidate counts:")
    for p in args.candidates:
        if not p.exists():
            print(f"  {p}: missing (skipped)")
            continue
        n = len(load(p))
        print(f"  {p}: {n} (delta vs ref min={n - min(ref_counts.values())})")


if __name__ == "__main__":
    main()
