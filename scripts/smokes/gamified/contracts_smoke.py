#!/usr/bin/env python3
import sys
import runpy
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main():
    rr = str(repo_root())
    if rr not in sys.path:
        sys.path.insert(0, rr)
    runpy.run_module("prototypes.gamified.smokes.contracts_smoke", run_name="__main__")


if __name__ == "__main__":
    main()
