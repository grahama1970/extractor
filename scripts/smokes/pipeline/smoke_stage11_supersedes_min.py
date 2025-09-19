#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "numpy>=2.0.0",
#   "loguru>=0.7.0,<0.8",
#   "python-dotenv>=1.0.0,<2",
#   "litellm>=1.74.7",
#   "numpy>=2.0.0",
# ]
# ///
"""Smoke: Stage 11 emits 'supersedes' edges when revisions exist.

Build a minimal Stage 10 flattened JSON with two objects sharing doc_id and
section_id but different revision_id (v1→v2). Assert a 'supersedes' edge.
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
    out_dir = Path("data/results/cli_smokes/supersedes").resolve()
    stage11 = out_dir / "11_arango_create_graph/json_output"
    tmp = out_dir / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    # Two objects, same doc/section, different revisions
    flat = tmp / "10_flattened.json"
    data = [
        {"_key": "k1", "doc_id": "D", "section_id": "S1", "revision_id": "v1", "text_content": "alpha"},
        {"_key": "k2", "doc_id": "D", "section_id": "S1", "revision_id": "v2", "text_content": "alpha"},
    ]
    flat.write_text(json.dumps(data, indent=2))

    # Run Stage 11
    env = dict(**os.environ)
    src_dir = str((Path(__file__).resolve().parents[3] / "src").resolve())
    env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH','')}"
    stage11.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "extractor.pipeline.steps.11_arango_create_graph", "run", str(flat), "-o", str(out_dir), "--skip-graph-creation"]
    if subprocess.run(cmd, env=env).returncode != 0:
        typer.echo("Stage 11 run failed", err=True)
        raise typer.Exit(1)

    edges = json.loads((stage11 / "11_graph_edges.json").read_text())
    ok = any(e.get("relationship_type") == "supersedes" for e in edges)
    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts")/"stage11_supersedes.json").write_text(json.dumps({"ok": ok, "edges": len(edges)}, indent=2))
    if not ok:
        typer.echo("No 'supersedes' edge found", err=True)
        raise typer.Exit(1)
    print("OK: supersedes edges present")


if __name__ == "__main__":
    app()

