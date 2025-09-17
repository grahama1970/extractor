#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""HTML: table header row detected in Stage 07 table.headers."""

from __future__ import annotations

import json
from pathlib import Path
import typer

from extractor.pipeline.structured_pipeline import STRUCTURED_PIPELINES, run_structured_pipeline
from extractor.core.providers.html import HTMLProvider

app = typer.Typer(add_completion=False)


@app.command()
def main(tmp_dir: Path = typer.Option(Path("data/results/structured_parity_smoke/html_synth"))):
    tmp_dir.mkdir(parents=True, exist_ok=True)
    html_path = tmp_dir / "table_headers.html"
    html_path.write_text(
        """
        <html><body>
          <h1>Doc</h1>
          <table>
            <tr><th>A</th><th>B</th></tr>
            <tr><td>1</td><td>2</td></tr>
          </table>
        </body></html>
        """.strip(),
        encoding="utf-8",
    )
    meta = STRUCTURED_PIPELINES[HTMLProvider]
    artifacts = run_structured_pipeline(HTMLProvider, html_path, tmp_dir, stage_prefix=meta.stage_prefix, skip_export10=True, skip_embeddings10=True, fast_embeddings10=True)
    s07 = json.loads(Path(artifacts["stage07"]).read_text())
    secs = s07.get("reflowed_sections") or []
    assert secs, "No sections for HTML table headers"
    tables = secs[0].get("tables") or []
    assert tables, "No tables captured in Stage 07"
    headers = tables[0].get("headers") or []
    if 0 not in headers:
        typer.echo(f"Expected header row 0; got {headers}", err=True)
        raise typer.Exit(code=1)
    typer.echo("HTML table header detection passed.")


if __name__ == "__main__":
    app()

