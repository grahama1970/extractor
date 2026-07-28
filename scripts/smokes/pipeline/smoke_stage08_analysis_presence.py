#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv",
# ]
# ///
from __future__ import annotations
import json
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)


@app.command()
def main(
    theorems: Path = typer.Option(..., exists=True, help="Stage 08 theorems (08_theorems.json)"),
):
    """Validate proof results from theorems file."""
    data = json.loads(theorems.read_text())
    pr = data.get("proof_results") if isinstance(data, dict) else None
    if not isinstance(pr, list) or not pr:
        raise typer.Exit(1)
    # Ensure at least one analysis block is present with normalized_prop
    found = False
    for e in pr:
        ana = e.get("analysis") if isinstance(e, dict) else None
        if isinstance(ana, dict) and ana.get("normalized_prop"):
            found = True
            break
    if not found:
        typer.echo("No analysis.normalized_prop present", err=True)
        raise typer.Exit(1)
    typer.echo("OK: analysis present in Stage 08 output")


if __name__ == "__main__":
    app()
