#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""XML provider: parse fallback should mark wrapped_root in metadata."""

from __future__ import annotations

import json
from pathlib import Path
import typer

from extractor.pipeline.structured_pipeline import STRUCTURED_PIPELINES, run_structured_pipeline
from extractor.core.providers.xml import XMLProvider

app = typer.Typer(add_completion=False)


@app.command()
def main(
    xml_path: Path = typer.Option(Path("data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.xml"), exists=True),
    results_dir: Path = typer.Option(Path("data/results/structured_parity_smoke/xml_checks")),
):
    meta = STRUCTURED_PIPELINES[XMLProvider]
    artifacts = run_structured_pipeline(XMLProvider, xml_path, results_dir, stage_prefix=meta.stage_prefix, skip_export10=True, skip_embeddings10=True, fast_embeddings10=True)
    s07 = json.loads(Path(artifacts["stage07"]).read_text())
    unified = s07.get("unified_document") or {}
    fmt = (unified.get("metadata") or {}).get("format_metadata") or {}
    if not fmt.get("wrapped_root"):
        typer.echo("XML provider did not set wrapped_root after fallback parse.", err=True)
        raise typer.Exit(code=1)
    typer.echo("XML parse fallback wrapped_root flag present.")


if __name__ == "__main__":
    app()

