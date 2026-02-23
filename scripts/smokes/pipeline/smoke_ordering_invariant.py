#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""Ordering invariant: flattened object_index_in_doc is strictly increasing and preserves input order on a simple doc."""

from __future__ import annotations

import json
from pathlib import Path
import typer

from extractor.pipeline.structured_pipeline import STRUCTURED_PIPELINES, run_structured_pipeline
from extractor.core.providers.html import HTMLProvider

app = typer.Typer(add_completion=False)


@app.command()
def main(tmp_dir: Path = typer.Option(Path("data/results/structured_parity_smoke/ordering"))):
    tmp_dir.mkdir(parents=True, exist_ok=True)
    html_path = tmp_dir / "order.html"
    html_path.write_text(
        """
        <html><body>
          <h1>Doc</h1>
          <p>First</p>
          <p>Second</p>
          <p>Third</p>
        </body></html>
        """.strip(),
        encoding="utf-8",
    )
    meta = STRUCTURED_PIPELINES[HTMLProvider]
    artifacts = run_structured_pipeline(
        HTMLProvider,
        html_path,
        tmp_dir,
        stage_prefix=meta.stage_prefix,
        skip_export10=True,
        skip_embeddings10=True,
        fast_embeddings10=True,
    )
    flat = json.loads(Path(artifacts["stage10_flattened"]).read_text())
    idxs = [o.get("object_index_in_doc") for o in flat]
    if any(i is None for i in idxs):
        typer.echo("Missing object_index_in_doc.", err=True)
        raise typer.Exit(code=1)
    if idxs != sorted(idxs):
        typer.echo(f"object_index_in_doc is not strictly increasing: {idxs}", err=True)
        raise typer.Exit(code=1)
    # Ensure first few text contents reflect linear order
    texts = [o.get("text_content") for o in flat if o.get("object_type") == "Text"]
    if not any("First" in t for t in texts[:2]):
        typer.echo("Ordering of paragraphs not preserved in first items.", err=True)
        raise typer.Exit(code=1)
    typer.echo("Ordering invariant preserved.")


if __name__ == "__main__":
    app()
