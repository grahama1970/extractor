#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""DOCX → PDF fallback success smoke.

Asserts that a mangled DOCX triggers PDF conversion and produces Stage 07/10
outputs under the PDF pipeline directories.
"""

from __future__ import annotations

import json
from pathlib import Path
import typer

from extractor.pipeline.structured_pipeline import STRUCTURED_PIPELINES, run_structured_pipeline
from extractor.core.providers.docx import DOCXProvider

app = typer.Typer(add_completion=False)


@app.command()
def main(
    docx_path: Path = typer.Option(
        Path(
            "data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.docx"
        ),
        exists=True,
    ),
    results_dir: Path = typer.Option(Path("data/results/structured_parity_smoke/docx_fallback")),
):
    meta = STRUCTURED_PIPELINES[DOCXProvider]
    artifacts = run_structured_pipeline(
        DOCXProvider,
        docx_path,
        results_dir,
        stage_prefix=meta.stage_prefix,
        skip_export10=True,
        skip_embeddings10=True,
        fast_embeddings10=True,
        auto_convert_mangled_docx=True,
    )
    # Accept either: direct return of PDF paths, or structured path return but PDF fallback artifacts exist
    Path(artifacts["stage07"]).resolve()
    Path(artifacts["stage10_flattened"]).resolve()
    # Look for PDF fallback outputs regardless of return
    pdf_root = results_dir / docx_path.stem
    pdf07 = pdf_root / "07_reflow_section" / "json_output" / "07_reflowed.json"
    pdf10 = pdf_root / "10_arangodb_exporter" / "json_output" / "10_flattened_data.json"
    if not pdf07.exists() or not pdf10.exists():
        typer.echo(f"PDF fallback outputs not found at {pdf07} and {pdf10}", err=True)
        raise typer.Exit(code=1)
    payload = json.loads(pdf07.read_text())
    diags = payload.get("diagnostics") or []
    mangled = any(
        isinstance(d, dict)
        and d.get("structured_pipeline") == "docx_mangled_check"
        and d.get("mangled_docx")
        for d in diags
    )
    if not mangled:
        typer.echo("Mangled diagnostic not recorded in Stage 07 payload.", err=True)
        raise typer.Exit(code=1)
    typer.echo("DOCX→PDF fallback success verified.")


if __name__ == "__main__":
    app()
