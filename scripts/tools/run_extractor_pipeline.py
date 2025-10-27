#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "loguru>=0.7.0",
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Deprecated location — use the in-package runner instead.

New canonical entry:
  python -m extractor.pipeline --pdf <file.pdf> --out data/results/pipeline

This shim forwards arguments to `src/extractor/pipeline/run_pipeline.py`
to avoid breaking existing local scripts while we consolidate tools
under the package.
"""

from __future__ import annotations

import sys
from extractor.pipeline.run_pipeline import main as _main


def main() -> int:  # pragma: no cover
    print(
        "[DEPRECATED] Use `python -m extractor.pipeline` instead of scripts/tools/run_extractor_pipeline.py",
        file=sys.stderr,
    )
    return _main()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
