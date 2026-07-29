#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv",
#   "loguru",
#   "pymupdf",        # import as 'fitz'
#   "pillow",         # import as 'PIL'
#   "urlextract",
#   "strip-tags",
#   "json-repair",
#   "litellm",
# ]
# ///
"""Smoke: Lean4 proving via unified CLI (--prove) produces 08_theorems.json.

Skips gracefully when the Lean4 CLI is not available.
"""
from __future__ import annotations
import os

import json
from pathlib import Path
import subprocess
import sys
import typer

app = typer.Typer(add_completion=False)


@app.command()
def main(
    pdf: Path = typer.Option(Path("data/input/pipeline/BHT_CV32A65X_marked.pdf"), exists=True),
    out_dir: Path = typer.Option(Path("data/results/cli_smokes/lean4_prove")),
    lean4_cli: Path = typer.Option(
        Path(os.environ.get("LEAN4_CLI", Path.home() / "workspace/experiments/lean4/src/lean4_prover/cli_mini.py"))
    ),
):
    """Run Lean4 CLI to process PDF, saving results."""
    if not lean4_cli.exists():
        print("SKIP: Lean4 CLI not found; skipping prove smoke.")
        raise typer.Exit(0)
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "src.cli",
        "extract",
        str(pdf),
        str(out_dir),
        "--mode",
        "accurate",
        "--prove",
    ]
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        typer.echo("CLI accurate --prove failed", err=True)
        raise typer.Exit(1)
    theorems = out_dir / "08_lean4_theorem_prover" / "json_output" / "08_theorems.json"
    if not theorems.exists():
        typer.echo(f"Missing Lean4 theorems JSON: {theorems}", err=True)
        raise typer.Exit(1)
    data = json.loads(theorems.read_text())
    # Write a tiny artifact with counts
    art = Path("scripts/artifacts")
    art.mkdir(parents=True, exist_ok=True)
    (art / "lean4_prove_summary.json").write_text(
        json.dumps(
            {
                "path": str(theorems),
                "keys": list(data.keys()),
            },
            indent=2,
        )
    )
    print("OK: Lean4 theorems JSON present")


if __name__ == "__main__":
    app()
