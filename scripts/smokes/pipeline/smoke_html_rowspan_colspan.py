#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""HTML: complex table with rowspan/colspan yields sensible row/col counts and header presence."""

from __future__ import annotations

import json
from pathlib import Path
import typer

from extractor.pipeline.structured_pipeline import STRUCTURED_PIPELINES, run_structured_pipeline
from extractor.core.providers.html import HTMLProvider

app = typer.Typer(add_completion=False)


@app.command()
def main(tmp_dir: Path = typer.Option(Path("data/results/structured_parity_smoke/html_synth"))):
    """Create and populate an HTML file in the specified directory."""
    tmp_dir.mkdir(parents=True, exist_ok=True)
    html_path = tmp_dir / "rowcolspan.html"
    html_path.write_text(
        """
        <html><body>
          <h1>Doc</h1>
          <table>
            <tr><th colspan="2">Header</th></tr>
            <tr><td rowspan="2">A</td><td>B</td></tr>
            <tr><td>C</td></tr>
          </table>
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
    secs = s07.get("reflowed_sections") or []
    assert secs, "No sections built"
    tabs = secs[0].get("tables") or []
    assert tabs, "No tables found"
    t = tabs[0]
    if (t.get("rows", 0) < 2) or (t.get("cols", 0) < 2):
        typer.echo(
            f"Unexpected small table dims rows={t.get('rows')} cols={t.get('cols')}", err=True
        )
        raise typer.Exit(code=1)
    headers = t.get("headers") or []
    if 0 not in headers:
        typer.echo("Expected header row index 0 in complex table.", err=True)
        raise typer.Exit(code=1)
    typer.echo("HTML rowspan/colspan table mapping passed.")


if __name__ == "__main__":
    app()
