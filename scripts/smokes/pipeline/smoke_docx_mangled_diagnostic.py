#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""DOCX: verify mangled diagnostic is recorded in Stage 07."""

from __future__ import annotations

import json
from pathlib import Path
import typer

from extractor.pipeline.structured_pipeline import STRUCTURED_PIPELINES, run_structured_pipeline
from extractor.core.providers.docx import DOCXProvider

app = typer.Typer(add_completion=False)


@app.command()
def main(
    docx_path: Path = typer.Option(Path("data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.docx"), exists=True),
    results_dir: Path = typer.Option(Path("data/results/structured_parity_smoke/docx_checks")),
):
    meta = STRUCTURED_PIPELINES[DOCXProvider]
    artifacts = run_structured_pipeline(DOCXProvider, docx_path, results_dir, stage_prefix=meta.stage_prefix, skip_export10=True, skip_embeddings10=True, fast_embeddings10=True, auto_convert_mangled_docx=True)
    s07 = json.loads(Path(artifacts["stage07"]).read_text())
    diags = s07.get("diagnostics") or []
    found = any(isinstance(d, dict) and d.get("structured_pipeline") == "docx_mangled_check" and d.get("mangled_docx") for d in diags)
    if not found:
        typer.echo("DOCX mangled diagnostic not present in Stage 07 payload.", err=True)
        raise typer.Exit(code=1)
    typer.echo("DOCX mangled diagnostic present in Stage 07.")


if __name__ == "__main__":
    app()

