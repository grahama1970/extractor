#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "loguru>=0.7.0,<0.8",
#   "python-dotenv>=1.0.0,<2",
# ]
# ///
"""Smoke: Stage 14 report includes graph counts from 11_graph_summary.json.

Creates a minimal results directory with a Stage 11 summary and runs the Stage
14 report generator, then asserts final_report.json contains stats.graph keys.
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
    out_dir = Path("data/results/cli_smokes/stage14_graph").resolve()
    stage11 = out_dir / "11_arango_create_graph/json_output"
    stage11.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema_version": "edge_v1",
        "total_edges": 2,
        "counts_by_type": {"semantic_similarity": 2},
        "violations_count": 0,
    }
    (stage11 / "11_graph_summary.json").write_text(json.dumps(summary, indent=2))
    # Put a minimal confirmation file so loader picks up the stage
    (stage11 / "11_graph_confirmation.json").write_text(json.dumps({"status": "Completed"}, indent=2))

    # Run Stage 14
    env = dict(**os.environ)
    src_dir = str((Path(__file__).resolve().parents[3] / "src").resolve())
    env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH','')}"
    cmd = [sys.executable, "-m", "extractor.pipeline.steps.14_report_generator", "run", str(out_dir)]
    if subprocess.run(cmd, env=env).returncode != 0:
        typer.echo("Stage 14 run failed", err=True)
        raise typer.Exit(1)

    final = json.loads((out_dir / "final_report.json").read_text())
    stats = final.get("pipeline_statistics", {}) if isinstance(final, dict) else {}
    ok = isinstance(stats, dict)
    g = stats.get("graph", {}) if ok else {}
    ok = ok and "edge_counts_by_type" in g and "violations_count" in g
    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts")/"stage14_graph_counts.json").write_text(json.dumps({"ok": ok, "graph": g}, indent=2))
    if not ok:
        typer.echo("Graph counts missing in final report", err=True)
        raise typer.Exit(1)
    print("OK: Stage 14 graph stats present")


if __name__ == "__main__":
    app()
