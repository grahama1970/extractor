#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""Markdown vs PDF parity smoke (sections + section-context)."""

from __future__ import annotations

import json
from pathlib import Path
import typer

from extractor.pipeline.structured_pipeline import STRUCTURED_PIPELINES, run_structured_pipeline
from extractor.core.providers.markdown import MarkdownProvider

app = typer.Typer(add_completion=False)


@app.command()
def main(
    md_path: Path = typer.Option(
        Path(
            "data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.md"
        ),
        exists=True,
    ),
    results_dir: Path = typer.Option(Path("data/results/structured_parity_smoke/markdown")),
):
    """Run a structured pipeline using a specified Markdown file."""
    meta = STRUCTURED_PIPELINES[MarkdownProvider]
    artifacts = run_structured_pipeline(
        MarkdownProvider,
        md_path,
        results_dir,
        stage_prefix=meta.stage_prefix,
        skip_export10=True,
        skip_embeddings10=True,
        fast_embeddings10=True,
    )
    s07 = json.loads(Path(artifacts["stage07"]).read_text())
    sections = s07.get("reflowed_sections") or []
    if not sections:
        typer.echo("No sections in Markdown Stage 07.", err=True)
        raise typer.Exit(code=1)
    flat = json.loads(Path(artifacts["stage10_flattened"]).read_text())
    has_section_context = any(
        isinstance(obj, dict) and str(obj.get("section_id") or "") not in ("", "document-root")
        for obj in flat
    )
    if not has_section_context:
        typer.echo("No non-root section_id in Stage 10 flattened (Markdown).", err=True)
        raise typer.Exit(code=1)
    typer.echo("Markdown parity section + section-context checks passed.")


if __name__ == "__main__":
    app()
