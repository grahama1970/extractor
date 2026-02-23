#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""PPTX: sections count should match slide_count metadata."""

from __future__ import annotations

import json
from pathlib import Path
import typer

from extractor.pipeline.structured_pipeline import STRUCTURED_PIPELINES, run_structured_pipeline
from extractor.core.providers.pptx import PPTXProvider

app = typer.Typer(add_completion=False)


@app.command()
def main(
    pptx_path: Path = typer.Option(
        Path(
            "data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.pptx"
        ),
        exists=True,
    ),
    results_dir: Path = typer.Option(Path("data/results/structured_parity_smoke/pptx_checks")),
):
    meta = STRUCTURED_PIPELINES[PPTXProvider]
    artifacts = run_structured_pipeline(
        PPTXProvider,
        pptx_path,
        results_dir,
        stage_prefix=meta.stage_prefix,
        skip_export10=True,
        skip_embeddings10=True,
        fast_embeddings10=True,
    )
    s07 = json.loads(Path(artifacts["stage07"]).read_text())
    sections = s07.get("reflowed_sections") or []
    unified = s07.get("unified_document") or {}
    fmt = (unified.get("metadata") or {}).get("format_metadata") or {}
    slide_count = int(fmt.get("slide_count") or 0)
    if slide_count == 0:
        typer.echo(
            "PPTX unified_document.metadata.format_metadata.slide_count missing or zero.", err=True
        )
        raise typer.Exit(code=1)
    if len(sections) != slide_count:
        typer.echo(
            f"Section count mismatch: sections={len(sections)} slide_count={slide_count}", err=True
        )
        raise typer.Exit(code=1)
    typer.echo("PPTX sections vs slide_count check passed.")


if __name__ == "__main__":
    app()
