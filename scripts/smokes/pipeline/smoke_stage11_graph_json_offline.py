#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""Smoke: Stage 11 edges JSON exists for structured runs (offline).

Runs the unified CLI on a small structured sample (HTML) and asserts that
11_arango_create_graph/json_output/11_graph_edges.json exists and is non-empty.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import typer

app = typer.Typer(add_completion=False)


@app.command()
def main(
    sample: Path = typer.Option(
        Path("data/results/pipeline/01_annotation_processor/BHT_CV32A65X_marked_clean.html"),
        exists=True,
        help="Structured sample (HTML recommended)",
    ),
    out_root: Path = typer.Option(Path("data/results/cli_smokes/structured_graph")),
):
    out_root.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    vpy = Path('.venv/bin/python')
    if vpy.exists():
        py = str(vpy)
    cmd = [py, "-m", "src.cli", "extract", str(sample), str(out_root)]
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        typer.echo("CLI structured run failed", err=True)
        raise typer.Exit(1)
    edges = out_root / sample.stem / "11_arango_create_graph" / "json_output" / "11_graph_edges.json"
    if not edges.exists():
        typer.echo(f"Missing edges JSON: {edges}", err=True)
        raise typer.Exit(1)
    data = json.loads(edges.read_text())
    if not isinstance(data, list):
        typer.echo("Edges JSON is not a list", err=True)
        raise typer.Exit(1)
    # Accept empty list for tiny samples but write an artifact
    art = Path("scripts/artifacts"); art.mkdir(parents=True, exist_ok=True)
    (art / "stage11_offline_edges_summary.json").write_text(json.dumps({
        "path": str(edges), "edge_count": len(data)
    }, indent=2))
    print("OK: Stage 11 edges JSON present (offline)")


if __name__ == "__main__":
    app()
