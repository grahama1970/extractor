#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Debug harness for Stage 11 (Arango Graph — bundle path)."""
from __future__ import annotations

import argparse
from pathlib import Path

from extractor.pipeline.steps import _11_arango_create_graph as stage11


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--bundle", type=Path, required=True, help="Bundle with documents[] (flattened pdf_objects)"
    )
    ap.add_argument("--out", type=Path, required=True, help="Results root (pipeline)")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--thr", type=float, default=0.55)
    args = ap.parse_args()

    stage11.debug_bundle(
        bundle=args.bundle,
        output_dir=args.out,
        k_neighbors=int(args.k),
        similarity_threshold=float(args.thr),
    )
    print("stage11:done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
