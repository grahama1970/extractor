#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""CLI smoke: extract --mode fast (PDF) produces <stem>_fast.json."""

from __future__ import annotations

import subprocess
from pathlib import Path
import sys
import typer

app = typer.Typer(add_completion=False)


@app.command()
def main(
    input_pdf: Path = typer.Option(Path("data/results/pipeline/01_annotation_processor/BHT_CV32A65X_marked_clean.pdf"), exists=True),
    output_dir: Path = typer.Option(Path("data/results/cli_smokes/fast_pdf")),
):
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "src.cli", "extract", "--mode", "fast", str(input_pdf), str(output_dir)]
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        typer.echo("CLI fast extract failed.", err=True)
        raise typer.Exit(code=1)
    out = output_dir / f"{input_pdf.stem}_fast.json"
    if not out.exists():
        typer.echo(f"Expected fast output missing: {out}", err=True)
        raise typer.Exit(code=1)
    typer.echo("CLI fast PDF smoke passed.")


if __name__ == "__main__":
    app()

