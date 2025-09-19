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
"""Smoke: Stage 11 emits 'duplicates' edges for identical text.

Build a minimal Stage 10 flattened JSON with two identical text objects in the
same section/doc and assert a 'duplicates' edge.
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
    out_dir = Path("data/results/cli_smokes/duplicates").resolve()
    stage11 = out_dir / "11_arango_create_graph/json_output"
    tmp = out_dir / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    flat = tmp / "10_flattened.json"
    data = [
        {"_key": "k1", "doc_id": "D", "section_id": "S1", "text_content": "Same line"},
        {"_key": "k2", "doc_id": "D", "section_id": "S1", "text_content": "Same line"},
    ]
    flat.write_text(json.dumps(data, indent=2))

    env = dict(**os.environ)
    src_dir = str((Path(__file__).resolve().parents[3] / "src").resolve())
    env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH','')}"
    stage11.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "extractor.pipeline.steps.11_arango_create_graph", "run", str(flat), "-o", str(out_dir), "--skip-graph-creation"]
    if subprocess.run(cmd, env=env).returncode != 0:
        typer.echo("Stage 11 run failed", err=True)
        raise typer.Exit(1)

    edges = json.loads((stage11 / "11_graph_edges.json").read_text())
    ok = any(e.get("relationship_type") == "duplicates" for e in edges)
    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts")/"stage11_duplicates.json").write_text(json.dumps({"ok": ok, "edges": len(edges)}, indent=2))
    if not ok:
        typer.echo("No 'duplicates' edge found", err=True)
        raise typer.Exit(1)
    print("OK: duplicates edges present")


if __name__ == "__main__":
    app()

