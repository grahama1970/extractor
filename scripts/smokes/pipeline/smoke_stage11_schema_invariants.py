#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "numpy>=2.0.0",
#   "loguru>=0.7.0,<0.8",
#   "python-dotenv>=1.0.0,<2",
#   "litellm>=1.74.7",
#   "pillow>=10.1.0,<11.0.0",
#   "urlextract>=1.9.0",
#   "strip_tags>=0.6",
#   "json-repair>=0.44.1",
# ]
# ///
"""Smoke: Stage 11 writes a summary with schema/invariants validation.

Runs the unified CLI in accurate offline mode (fast embeddings skipped) to
produce Stage 11 outputs, then checks for 11_graph_summary.json and basic keys.
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
    out_dir = Path("data/results/cli_smokes/schema_invariants").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Construct a minimal debug-bundle with two docs and tiny embeddings
    bundle_dir = out_dir / "tmp"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    docs = [
        {"_key": "a", "section_id": "S1", "source_pdf": "x.pdf", "text_content": "alpha", "embedding": [1.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0]},
        {"_key": "b", "section_id": "S2", "source_pdf": "x.pdf", "text_content": "alphabet", "embedding": [0.9,0.1,0.0,0.0,0.0,0.0,0.0,0.0]},
    ]
    bundle = bundle_dir / "bundle.json"
    bundle.write_text(json.dumps({"documents": docs}, indent=2))

    # Run Stage 11 debug-bundle
    env = dict(**os.environ)
    src_dir = str((Path(__file__).resolve().parents[3] / "src").resolve())
    env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH','')}"
    cmd = [sys.executable, "-m", "extractor.pipeline.steps.11_arango_create_graph", "debug-bundle", str(bundle), "-o", str(out_dir)]
    rc = subprocess.run(cmd, env=env).returncode
    if rc != 0:
        typer.echo("Stage 11 debug-bundle failed", err=True)
        raise typer.Exit(1)

    summary = out_dir / "11_arango_create_graph/json_output/11_graph_summary.json"
    if not summary.exists():
        typer.echo("Stage 11 summary not found", err=True)
        raise typer.Exit(1)
    data = json.loads(summary.read_text())
    required_keys = {"schema_version", "total_edges", "counts_by_type", "violations_count"}
    if not required_keys.issubset(set(data.keys())):
        typer.echo(f"Summary missing keys: {required_keys - set(data.keys())}", err=True)
        raise typer.Exit(1)

    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts")/"stage11_schema_summary.json").write_text(json.dumps(data, indent=2))
    print("OK: Stage 11 schema/invariants summary present")


if __name__ == "__main__":
    app()
