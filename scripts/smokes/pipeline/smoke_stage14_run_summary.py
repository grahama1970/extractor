#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""Smoke: Stage 14 writes run_summary.json with key stats.

Creates a minimal results dir (Stage 11 edges + summary), runs Stage 14, and
asserts run_summary.json exists with expected keys.
"""
from __future__ import annotations

import json
from pathlib import Path
import os
import subprocess
import sys
import typer

app = typer.Typer(add_completion=False)


@app.command()
def main():
    """Create and populate a directory with graph summary JSON data."""
    out_dir = Path("data/results/cli_smokes/run_summary").resolve()
    stage11 = out_dir / "11_arango_create_graph/json_output"
    stage11.mkdir(parents=True, exist_ok=True)
    (stage11 / "11_graph_summary.json").write_text(
        json.dumps(
            {
                "schema_version": "edge_v1",
                "counts_by_type": {"semantic_similarity": 1},
                "violations_count": 0,
            },
            indent=2,
        )
    )
    (stage11 / "11_graph_edges.json").write_text(
        json.dumps(
            [
                {
                    "_from": "pdf_objects/a",
                    "_to": "pdf_objects/b",
                    "relationship_type": "semantic_similarity",
                    "weight": 0.9,
                }
            ],
            indent=2,
        )
    )
    (stage11 / "11_graph_confirmation.json").write_text(
        json.dumps({"status": "Completed"}, indent=2)
    )

    env = dict(**os.environ)
    src_dir = str((Path(__file__).resolve().parents[3] / "src").resolve())
    env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH','')}"
    cmd = [
        sys.executable,
        "-m",
        "extractor.pipeline.steps.14_report_generator",
        "run",
        str(out_dir),
    ]
    if subprocess.run(cmd, env=env).returncode != 0:
        typer.echo("Stage 14 run failed", err=True)
        raise typer.Exit(1)
    rs = out_dir / "run_summary.json"
    if not rs.exists():
        typer.echo("run_summary.json missing", err=True)
        raise typer.Exit(1)
    data = json.loads(rs.read_text())
    ok = (
        isinstance(data.get("graph"), dict)
        and "edge_counts_by_type" in data.get("graph", {})
        and isinstance(data.get("exporters"), dict)
    )
    if not ok:
        typer.echo("run_summary.json invalid", err=True)
        raise typer.Exit(1)
    print("OK: run_summary.json present with stats")


if __name__ == "__main__":
    app()
