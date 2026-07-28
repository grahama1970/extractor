#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""Smoke: Stage 11 emits 'refers_to' edges on simple inline references.

Two sections: S1 has content; S2 contains text 'see section S1'. Expect a
'refers_to' edge from S2 object to an object in S1.
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
    """Execute the main command for the application."""
    out_dir = Path("data/results/cli_smokes/refers_to").resolve()
    stage11 = out_dir / "11_arango_create_graph/json_output"
    tmp = out_dir / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    flat = tmp / "10_flattened.json"
    data = [
        {"_key": "k1", "doc_id": "D", "section_id": "S1", "text_content": "Alpha section"},
        {
            "_key": "k2",
            "doc_id": "D",
            "section_id": "S2",
            "text_content": "See section S1 for details",
        },
    ]
    flat.write_text(json.dumps(data, indent=2))

    env = dict(**os.environ)
    src_dir = str((Path(__file__).resolve().parents[3] / "src").resolve())
    env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH','')}"
    stage11.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "extractor.pipeline.steps.11_arango_create_graph",
        "run",
        str(flat),
        "-o",
        str(out_dir),
        "--skip-graph-creation",
    ]
    if subprocess.run(cmd, env=env).returncode != 0:
        typer.echo("Stage 11 run failed", err=True)
        raise typer.Exit(1)

    edges = json.loads((stage11 / "11_graph_edges.json").read_text())
    ok = any(e.get("relationship_type") == "refers_to" for e in edges)
    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts") / "stage11_refers_to.json").write_text(
        json.dumps({"ok": ok, "edges": len(edges)}, indent=2)
    )
    if not ok:
        typer.echo("No 'refers_to' edge found", err=True)
        raise typer.Exit(1)
    print("OK: refers_to edges present")


if __name__ == "__main__":
    app()
