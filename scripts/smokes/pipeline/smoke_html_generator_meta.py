#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""HTML: generator meta is captured in format_metadata."""

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
    html_path = tmp_dir / "gen.html"
    html_path.write_text(
        """
        <html><head><meta name="generator" content="pdftohtml 0.4"></head>
        <body><h1>Doc</h1><p>Para</p></body></html>
        """.strip(),
        encoding="utf-8",
    )
    meta = STRUCTURED_PIPELINES[HTMLProvider]
    artifacts = run_structured_pipeline(HTMLProvider, html_path, tmp_dir, stage_prefix=meta.stage_prefix, skip_export10=True, skip_embeddings10=True, fast_embeddings10=True)
    s07 = json.loads(Path(artifacts["stage07"]).read_text())
    unified = s07.get("unified_document") or {}
    fmt = (unified.get("metadata") or {}).get("format_metadata") or {}
    gen = str(fmt.get("generator") or "")
    if "pdftohtml" not in gen:
        typer.echo(f"generator meta missing; got '{gen}'", err=True)
        raise typer.Exit(code=1)
    typer.echo("HTML generator meta captured.")


if __name__ == "__main__":
    app()

