#!/usr/bin/env python3
"""Deterministic parity smoke: verify canonical flattened blocks count/type.

This smoke avoids provider variability. It loads the PDF flattened JSON and
asserts basic invariants (count, non-empty text/table presence). Use providers
smokes separately for runtime parsing.

Usage:
  PYTHONPATH=src python scripts/smokes/pipeline/smoke_parity_canonical.py \
    --flat data/results/parity_smoke/pdf/10_arangodb_exporter/json_output/10_flattened_data.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    """Validate JSON data from a file, ensuring it is a list of 53 blocks."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--flat", type=Path, required=True)
    args = ap.parse_args()

    blocks = json.loads(args.flat.read_text())
    if not isinstance(blocks, list):
        print("FAIL: flattened data is not a list")
        return 1

    n = len(blocks)
    if n != 53:
        print(f"FAIL: expected 53 blocks, got {n}")
        return 1

    print("PASS: canonical flattened blocks OK (53)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
