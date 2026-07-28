#!/usr/bin/env python3
import runpy
import sys
from pathlib import Path


def repo_root() -> Path:
    """Return the root directory path of the repository."""
    return Path(__file__).resolve().parents[2]


def main():
    # Bridge to canonical module under prototypes/gamified
    rr = str(repo_root())
    if rr not in sys.path:
        sys.path.insert(0, rr)
    runpy.run_module("prototypes.gamified.smokes.emit_aggregate_smoke", run_name="__main__")


if __name__ == "__main__":
    main()
