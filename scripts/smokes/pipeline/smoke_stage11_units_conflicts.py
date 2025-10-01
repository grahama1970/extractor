#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "numpy>=2.0.0",
#   "loguru>=0.7.0,<0.8",
#   "python-dotenv>=1.0.0,<2",
#   "pydantic>=2.4.2,<3",
#   "pydantic-settings>=2.0.3,<3",
#   "litellm>=1.74.7",
#   "pillow>=10.1.0,<11.0.0",
#   "urlextract>=1.9.0",
#   "strip_tags>=0.6",
#   "json-repair>=0.44.1",
#   "pint>=0.23",
# ]
# ///
"""Smoke: Units normalization yields 'conflicts_with' edges.

Constructs a minimal Stage 10 bundle with two objects in the same section:
  - "Mass is 5 kg"
  - "Mass is 4000 g"
Stage 11 should emit at least one 'conflicts_with' edge.
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
    out_dir = Path("data/results/cli_smokes/units_conflicts").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build a minimal Stage 10 debug-bundle input (UnifiedDocument-like)
    # We pass via Stage 10 to allow units normalization to populate each object.
    tmp = out_dir / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    # Minimal 'reflowed_sections' with two paragraphs under section S1
    # Build unified_document payload (preferred by Stage 10 coercion)
    reflow = {
        "unified_document": {
            "id": "doc-1",
            "source_path": "units_conflicts.pdf",
            "metadata": {"title": "Units Doc", "format_metadata": {"source_pdf": "units_conflicts.pdf"}},
            "source_type": "pdf",
            "hierarchy": {"id": "root", "block_id": "h0", "title": "Spec", "level": 0, "children": [
                {"id": "S1", "block_id": "h1", "title": "Spec", "level": 1, "children": []}
            ]},
            "blocks": [
                {"id": "b1", "parent_id": "h1", "type": "paragraph", "content": "Mass is 5 kg", "metadata": {"page_number": 1, "bbox": [0,0,10,10]}},
                {"id": "b2", "parent_id": "h1", "type": "paragraph", "content": "Mass is 4000 g", "metadata": {"page_number": 1, "bbox": [0,10,10,20]}},
            ]
        }
    }
    bundle10 = tmp / "bundle10.json"
    bundle10.write_text(json.dumps(reflow, indent=2))

    # Run Stage 10 debug-bundle to produce 10_flattened_data.json
    env = dict(**os.environ)
    src_dir = str((Path(__file__).resolve().parents[3] / "src").resolve())
    env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH','')}"
    cmd10 = [sys.executable, "-m", "extractor.pipeline.steps.10_arangodb_exporter", "debug-bundle", str(bundle10), "-o", str(out_dir), "--skip-embeddings", "--fast-embeddings"]
    if subprocess.run(cmd10, env=env).returncode != 0:
        typer.echo("Stage 10 debug-bundle failed", err=True)
        raise typer.Exit(1)

    # Run Stage 11 on the flattened JSON
    flat = out_dir / "10_arangodb_exporter/json_output/10_flattened_data.json"
    cmd11 = [sys.executable, "-m", "extractor.pipeline.steps.11_arango_create_graph", "run", str(flat), "-o", str(out_dir), "--skip-graph-creation"]
    if subprocess.run(cmd11, env=env).returncode != 0:
        typer.echo("Stage 11 run failed", err=True)
        raise typer.Exit(1)

    edges_path = out_dir / "11_arango_create_graph/json_output/11_graph_edges.json"
    edges = json.loads(edges_path.read_text()) if edges_path.exists() else []
    conflicts = [e for e in edges if e.get("relationship_type") == "conflicts_with"]
    if not conflicts:
        typer.echo("Expected at least one 'conflicts_with' edge", err=True)
        raise typer.Exit(1)

    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts")/"stage11_units_conflicts.json").write_text(json.dumps({"conflicts": len(conflicts)}, indent=2))
    print("OK: conflicts_with edges present")


if __name__ == "__main__":
    app()
