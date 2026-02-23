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
import importlib.util
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(
    add_completion=False, help="Smoke: Stage 11 skip-graph-creation with no embeddings"
)


@app.command()
def main(results: Path = typer.Option(Path("data/results/pipeline"), "-o")) -> None:
    load_dotenv(find_dotenv() or None)
    # Prepare empty-embedding flattened data
    flat_dir = results / "10_arangodb_exporter" / "json_output"
    flat_dir.mkdir(parents=True, exist_ok=True)
    flat_path = flat_dir / "10_flattened_data.json"
    flat_path.write_text(
        json.dumps(
            [
                {
                    "_key": "k1",
                    "source_pdf": "fixture.pdf",
                    "object_index_in_doc": 0,
                    "object_type": "Text",
                    "text_content": "Hello",
                    "embedding": None,
                    "section_level": 1,
                    "section_breadcrumbs": ["Intro"],
                }
            ],
            indent=2,
        )
    )

    spec = importlib.util.spec_from_file_location(
        "stage11", "src/extractor/pipeline/steps/11_arango_create_graph.py"
    )
    if not spec or not spec.loader:
        raise SystemExit("Failed to load Stage 11 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]

    mod.run(
        input_json=flat_path,
        output_dir=results,
        k_neighbors=5,
        similarity_threshold=0.6,
        skip_graph_creation=True,
    )

    edges = results / "11_arango_create_graph" / "json_output" / "11_graph_edges.json"
    if not edges.exists():
        raise SystemExit("Edges JSON not written in skip-graph mode")
    data = json.loads(edges.read_text())
    if data != []:
        raise SystemExit("Edges should be empty when no embeddings present")
    typer.echo("OK: Stage 11 skip-graph wrote empty edges JSON")


if __name__ == "__main__":
    app()
