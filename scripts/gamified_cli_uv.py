#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "fastapi>=0.111.0",
#   "uvicorn>=0.30.0",
#   "httpx>=0.27.0",
#   "python-arango>=7.6.3",
#   "tenacity>=9.0.0",
#   "python-dotenv>=1.0.1",
# ]
# ///

"""
UV shim for the Gamified CLI.

Runs prototypes.gamified.cli Typer app with local repo imports enabled (adds ./src to sys.path).
Use this when you want zero Python env prep; uv will resolve the minimal deps above.

Examples:
  ./scripts/gamified_cli_uv.py run --codebase . --prompt "approaches: mul_shift_add, mul_karatsuba, mul_chunked"
  ./scripts/gamified_cli_uv.py status --run-id 20250101-120000
"""

import os
import sys
from pathlib import Path

# Ensure local src/ is importable (extractor, etc.)
repo_root = Path(__file__).resolve().parents[1]
src = repo_root / "src"
if src.exists():
    sys.path.insert(0, str(src))

# Run the Typer app
from prototypes.gamified.cli import app  # type: ignore

if __name__ == "__main__":
    app()
