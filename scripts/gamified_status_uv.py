#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///

"""
UV shim for the Gamified status command.

Convenience wrapper that invokes the Typer app with the 'status' command.
Adds ./src to sys.path so local packages import cleanly.
"""

import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
src = repo_root / "src"
if src.exists():
    sys.path.insert(0, str(src))

from prototypes.gamified.cli import app  # type: ignore

if __name__ == "__main__":
    if len(sys.argv) == 1 or sys.argv[1] != "status":
        sys.argv.insert(1, "status")
    app()
