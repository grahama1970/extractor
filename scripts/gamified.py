#!/usr/bin/env python3
"""
Legacy shim for the Gamified orchestrator CLI.

Canonical implementation now lives at `prototypes/gamified/cli.py`.
This wrapper re-exports the Typer `app` and commands to preserve existing
CLI entrypoints and CI scripts that invoke `scripts/gamified.py`.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository root is on sys.path so we can import the prototypes package
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from prototypes.gamified.cli import app, run, status  # type: ignore F401

__all__ = ["app", "run", "status"]

if __name__ == "__main__":
    app()
