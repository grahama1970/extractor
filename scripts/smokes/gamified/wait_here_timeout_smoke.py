#!/usr/bin/env python3
import sys
import runpy
from pathlib import Path


def repo_root() -> Path:
    """Return the root directory path of the repository."""
    return Path(__file__).resolve().parents[2]


def main():
    """Run a specific smoke test module after adding repo root to sys.path."""
    rr = str(repo_root())
    if rr not in sys.path:
        sys.path.insert(0, rr)
    runpy.run_module("prototypes.gamified.smokes.wait_here_timeout_smoke", run_name="__main__")


if __name__ == "__main__":
    main()
