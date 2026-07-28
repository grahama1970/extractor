#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""Smoke: JSON‑LD export v0

Creates a tiny Stage 10 dataset and an edges file, runs the JSON‑LD exporter,
and asserts the output contains @context and @graph with > 0 entries.
"""
from __future__ import annotations

import json
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)


@app.command()
def main():
    """Export JSON-LD data for CLI smoke testing."""
    import sys

    repo_src = (Path(__file__).resolve().parents[3] / "src").resolve()
    if str(repo_src) not in sys.path:
        sys.path.insert(0, str(repo_src))
    from extractor.pipeline.tools.jsonld_export import export_jsonld

    out_dir = Path("data/results/cli_smokes/jsonld").resolve()
    tmp = out_dir / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)

    # Minimal Stage 10 list
    stage10 = tmp / "10_flattened.json"
    objects = [
        {"_key": "o1", "doc_id": "d1", "section_id": "S1", "text_content": "A"},
        {"_key": "o2", "doc_id": "d1", "section_id": "S1", "text_content": "B"},
    ]
    stage10.write_text(json.dumps(objects, indent=2))

    # Minimal edges
    edges = tmp / "11_edges.json"
    edges.write_text(
        json.dumps(
            [
                {
                    "_from": "pdf_objects/o1",
                    "_to": "pdf_objects/o2",
                    "relationship_type": "semantic_similarity",
                    "weight": 0.9,
                }
            ],
            indent=2,
        )
    )

    out = out_dir / "graph.jsonld"
    res = export_jsonld(stage10, edges, out)
    data = json.loads(out.read_text())
    ok = (
        isinstance(data, dict)
        and "@context" in data
        and isinstance(data.get("@graph"), list)
        and len(data["@graph"]) >= 3
    )
    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts") / "jsonld_export_report.json").write_text(
        json.dumps({"ok": ok, **res}, indent=2)
    )
    if not ok:
        typer.echo("JSON‑LD export invalid", err=True)
        raise typer.Exit(1)
    print("OK: JSON‑LD export")


if __name__ == "__main__":
    app()
