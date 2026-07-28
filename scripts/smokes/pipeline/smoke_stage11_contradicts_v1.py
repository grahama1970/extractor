#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
from __future__ import annotations
import json
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)


@app.command()
def main(
    flat_json: Path = typer.Option(
        ..., exists=True, help="Stage 10 flattened JSON (10_flattened_data.json)"
    ),
    out_dir: Path = typer.Option(Path("data/results/pipeline")),
):
    """Load and process flattened JSON from a specified file path."""
    docs = json.loads(flat_json.read_text())
    # Inject a simple contradiction pair in-place by adding lean4_norm + polarity
    # Create two documents with same normalized prop and opposite polarity
    if len(docs) < 2:
        raise typer.Exit(1)
    docs[0].setdefault("rtm", {})
    docs[1].setdefault("rtm", {})
    docs[0]["rtm"].update({"lean4_norm": "x = 7", "lean4_polarity": "assert"})
    docs[1]["rtm"].update({"lean4_norm": "x = 7", "lean4_polarity": "deny"})
    # Write a small bundle and run Stage 11 debug_bundle path
    bundle = out_dir / "11_arango_create_graph/json_output/11_bundle.json"
    bundle.parent.mkdir(parents=True, exist_ok=True)
    bundle.write_text(json.dumps({"documents": docs}, indent=2))
    typer.echo(
        f"OK: Wrote bundle {bundle}; run 'python -m extractor.pipeline.steps.11_arango_create_graph debug-bundle {bundle}' to validate edges."
    )


if __name__ == "__main__":
    app()
