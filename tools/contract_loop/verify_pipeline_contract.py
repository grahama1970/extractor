#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "duckdb>=0.9.0",
# ]
# ///
"""Extractor CLI for the contract-loop core (uses the extractor adapter)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.contract_loop.core import DEFAULT_OUT, run_contract_loop  # noqa: E402


def validate_debug_args(args: argparse.Namespace) -> None:
    if args.debug and args.no_clean_downstream:
        raise ValueError("--debug requires downstream cleaning; drop --no-clean-downstream.")
    if args.debug and args.no_rerun_upstream:
        raise ValueError("--debug requires rerunning upstream steps; drop --no-rerun-upstream.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Fail-fast contract verifier for pipeline steps.")
    ap.add_argument("--pdf", type=Path, help="Input PDF path (required unless --verify-only)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Pipeline output directory")
    ap.add_argument("--fixture", type=Path, help="Fixture expectations JSON (optional)")
    ap.add_argument(
        "--mode",
        choices=["deterministic", "full"],
        default="deterministic",
        help="deterministic skips LLM steps; full runs all steps",
    )
    ap.add_argument("--verify-only", action="store_true", help="Only verify existing outputs")
    ap.add_argument("--max-tries", type=int, default=3, help="Max attempts per step")
    ap.add_argument(
        "--llm-judge",
        action="store_true",
        help="Run Codex judge for LLM outputs (fixture must enable per step)",
    )
    ap.add_argument("--llm-judge-model", type=str, help="Optional model name for Codex judge")
    ap.add_argument(
        "--min-requirements",
        type=int,
        default=1,
        help="Minimum rows required in requirements table",
    )
    ap.add_argument(
        "--skip-lean4",
        action="store_true",
        help="Skip Lean4 verification (even if fixture includes it)",
    )
    ap.add_argument(
        "--no-clean-downstream",
        action="store_true",
        help="Do not delete downstream outputs on retry",
    )
    ap.add_argument(
        "--no-rerun-upstream",
        action="store_true",
        help="Do not re-run upstream steps on retry",
    )
    ap.add_argument(
        "--start-step",
        type=str,
        help="Start loop from this step (validates upstream first)",
    )
    ap.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode: enforces clean/rerun, captures logs, verbose output",
    )
    ap.add_argument(
        "--bundle-warn-mb",
        type=int,
        default=50,
        help="Warn when collaboration bundle exceeds this size (MB).",
    )
    ap.add_argument(
        "--bundle-max-mb",
        type=int,
        default=100,
        help="Fail when collaboration bundle would exceed this size (MB).",
    )
    ap.add_argument(
        "--clarify-timeout",
        type=int,
        default=900,
        help="Clarify UI timeout in seconds (default 15 minutes).",
    )

    args = ap.parse_args()
    try:
        validate_debug_args(args)
    except ValueError as exc:
        ap.error(str(exc))

    if not args.verify_only and not args.pdf:
        ap.error("--pdf is required unless --verify-only is set")

    from tools.contract_loop.adapters.extractor import ExtractorAdapter  # noqa: E402

    adapter = ExtractorAdapter()
    return run_contract_loop(args, adapter)


if __name__ == "__main__":
    raise SystemExit(main())
