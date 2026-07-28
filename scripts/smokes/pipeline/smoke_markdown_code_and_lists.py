#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""Markdown: headings + lists make sections and list items become text in Stage 07 reflow.

Note: code fences are ignored by minimal provider; we focus on sections + lists.
"""

from __future__ import annotations

import json
from pathlib import Path
import typer

from extractor.pipeline.structured_pipeline import STRUCTURED_PIPELINES, run_structured_pipeline
from extractor.core.providers.markdown import MarkdownProvider

app = typer.Typer(add_completion=False)


@app.command()
def main(tmp_dir: Path = typer.Option(Path("data/results/structured_parity_smoke/markdown_synth"))):
    """Generate a synthetic markdown file with example lists and code."""
    tmp_dir.mkdir(parents=True, exist_ok=True)
    md_path = tmp_dir / "lists.md"
    md_path.write_text(
        """
        # Title

        - A
          - B
        1. C
        2. D

        ```python
        print('ignore')
        ```
        """.strip(),
        encoding="utf-8",
    )
    meta = STRUCTURED_PIPELINES[MarkdownProvider]
    artifacts = run_structured_pipeline(
        MarkdownProvider,
        md_path,
        tmp_dir,
        stage_prefix=meta.stage_prefix,
        skip_export10=True,
        skip_embeddings10=True,
        fast_embeddings10=True,
    )
    s07 = json.loads(Path(artifacts["stage07"]).read_text())
    secs = s07.get("reflowed_sections") or []
    if not secs:
        typer.echo("No sections in Markdown Stage 07.", err=True)
        raise typer.Exit(code=1)
    text = secs[0].get("reflowed_text") or ""
    for token in ["A", "B", "C", "D"]:
        if token not in text:
            typer.echo(f"Missing list token '{token}' in Markdown reflow", err=True)
            raise typer.Exit(code=1)
    typer.echo("Markdown headings+lists mapping passed.")


if __name__ == "__main__":
    app()
