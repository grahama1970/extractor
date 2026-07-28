#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Debug harness for Stage 01 (Annotation Processor)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from extractor.pipeline.steps import _01_annotation_processor as stage01


def main() -> int:
    """Parse command-line arguments for PDF processing and output paths."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path, required=True, help="Input PDF path")
    ap.add_argument("--out", type=Path, required=True, help="Results root (pipeline)")
    args = ap.parse_args()

    bundle = {
        "pdf": str(args.pdf.resolve()),
        "options": {},
    }
    tmp = args.out / "01_annotation_processor" / "_debug_bundle.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(bundle))
    stage01.debug_bundle(tmp, args.out)
    print("stage01:done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
