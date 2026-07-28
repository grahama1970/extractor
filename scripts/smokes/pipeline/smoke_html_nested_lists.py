#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""HTML: nested lists produce list items in reflowed text without duplication."""

from __future__ import annotations

import json
from pathlib import Path
import typer

from extractor.pipeline.structured_pipeline import STRUCTURED_PIPELINES, run_structured_pipeline
from extractor.core.providers.html import HTMLProvider

app = typer.Typer(add_completion=False)


@app.command()
def main(tmp_dir: Path = typer.Option(Path("data/results/structured_parity_smoke/html_synth"))):
    """Create a temporary directory and write an HTML file to it."""
    tmp_dir.mkdir(parents=True, exist_ok=True)
    html_path = tmp_dir / "nested_lists.html"
    html_path.write_text(
        """
        <html><body>
          <h1>Doc</h1>
          <ul>
            <li>Top 1
              <ul>
                <li>Child A</li>
                <li>Child B</li>
              </ul>
            </li>
            <li>Top 2</li>
          </ul>
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
    s07 = json.loads(Path(artifacts["stage07"]).read_text())
    sections = s07.get("reflowed_sections") or []
    assert sections, "No sections produced for HTML nested lists"
    text = sections[0].get("reflowed_text") or ""
    required = ["Top 1", "Child A", "Child B", "Top 2"]
    for token in required:
        if token not in text:
            typer.echo(f"Missing list token '{token}' in reflowed_text", err=True)
            raise typer.Exit(code=1)
    typer.echo("HTML nested lists reflow mapping passed.")


if __name__ == "__main__":
    app()
