#!/usr/bin/env python3
"""
Compatibility shim for legacy callers expecting `python -m extractor.pipeline.run_all`.

The original module accepted a richer flag set (e.g., --annotations-json, --clean-pdf).
This shim preserves the interface for external tools (e.g., tabbed pipeline bridge)
by tolerating those flags and delegating to the current run_pipeline entrypoint.

Notes:
- --annotations-json / --clean-pdf are accepted and ignored for now; they allow
  callers to continue passing user boxes without breaking. Upstream wiring should
  be migrated to `extractor.pipeline` with native support when available.
- Other flags are forwarded verbatim where supported by run_pipeline.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import run_pipeline


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Compatibility wrapper for run_pipeline")
    p.add_argument("--pdf", required=True, type=Path)
    p.add_argument("--results", "--out", dest="out", required=True, type=Path)
    p.add_argument("--annotations-json", type=str, help="Accepted for compatibility; currently ignored")
    p.add_argument("--clean-pdf", type=str, help="Accepted for compatibility; currently ignored")
    # Pass-through flags commonly used by callers
    p.add_argument("--stop-on-fail", action="store_true", default=False)
    p.add_argument("--skip-llm03", action="store_true")
    p.add_argument("--skip-descriptions06", action="store_true")
    p.add_argument("--summary-only07", dest="summary_only", action="store_true")
    p.add_argument("--skip-proving08", action="store_true")
    p.add_argument("--fast-embeddings10", action="store_true")
    p.add_argument("--offline", action="store_true")
    args, _extras = p.parse_known_args(argv)

    # Build argv for run_pipeline.main
    forwarded = [
        "--pdf", str(args.pdf),
        "--out", str(args.out),
    ]
    if args.stop_on_fail:
        forwarded.append("--stop-on-fail")
    if args.skip_llm03:
        forwarded.append("--skip-llm03")
    if args.skip_descriptions06:
        forwarded.append("--skip-fig-descriptions")
    if args.summary_only:
        forwarded.append("--summary-only")
    # run_pipeline does not have a skip-proving flag; proving is opt-in via --prove-requirements
    # fast-embeddings10 not supported in run_pipeline; ignore silently
    if args.offline:
        forwarded.append("--offline-smoke")

    return run_pipeline.main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
