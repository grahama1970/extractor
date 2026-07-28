#!/usr/bin/env python3
"""Tiny debug runner for Stage 14 (pure Python import-and-call).

Usage:
  python scripts/debug/stage14_debug.py --results data/results/pipeline
  python scripts/debug/stage14_debug.py --bundle scripts/artifacts/stage14_bundle.json --out data/results/pipeline
"""
import argparse
from pathlib import Path
from extractor.pipeline.steps import s14_report_generator as s14


def main():
    """Parse command-line arguments and execute corresponding pipeline operations."""
    p = argparse.ArgumentParser()
    p.add_argument("--results", type=Path)
    p.add_argument("--bundle", type=Path)
    p.add_argument("--out", type=Path, default=Path("data/results/pipeline"))
    args = p.parse_args()

    if args.results:
        out, result = s14.run_report(args.results)
        print(out)
    elif args.bundle:
        out, result = s14.debug_bundle(args.bundle, args.out)
        print(out)
    else:
        p.error("Provide --results or --bundle")


if __name__ == "__main__":
    main()
