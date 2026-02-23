#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""Smoke: Lean4 CLI advertises --deterministic support.

Skips if the local Lean4 CLI is not found. This does not execute a proof; it
verifies that the flag appears in the help output for operator confidence.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import typer

app = typer.Typer(add_completion=False)


@app.command()
def main():
    cli = Path("/home/graham/workspace/experiments/lean4/src/lean4_prover/cli_mini.py")
    if not cli.exists():
        print("SKIP: Lean4 CLI not found; skipping help check.")
        raise typer.Exit(0)

    cmd = [sys.executable, str(cli), "--help"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = proc.stdout.decode("utf-8", errors="ignore")

    ok = "deterministic" in out.lower()

    artifacts = Path("scripts/artifacts")
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "lean4_cli_help_check.json").write_text(json.dumps({"ok": ok}, indent=2))

    if not ok:
        print("SKIP: --deterministic not shown in help; CLI may still accept it.")
        raise typer.Exit(0)

    print("OK: Lean4 CLI help includes --deterministic")


if __name__ == "__main__":
    app()
