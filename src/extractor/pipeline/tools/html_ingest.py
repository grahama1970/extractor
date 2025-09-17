#!/usr/bin/env python3
"""HTML ingestion utility for the extraction pipeline.

This tool converts a raw HTML document into our canonical ``UnifiedDocument``
representation and optionally flattens it using the Stage 10 exporter logic so
we can diff results against the PDF pipeline.

Usage examples
--------------
::

    uv run src/extractor/pipeline/tools/html_ingest.py ingest \
        data/results/pipeline/01_annotation_processor/BHT_CV32A65X_marked_clean.html \
        --output-dir data/results/html_ingest --flatten

The command writes the unified document JSON plus the Stage 10 flattened output
under ``<output-dir>/<stem>/``.
"""

from __future__ import annotations

import json
import importlib.util
from pathlib import Path
from typing import Optional

import typer

from extractor.core.providers.html import HTMLProvider
from extractor.core.schema.unified_document import UnifiedDocument

app = typer.Typer(add_completion=False)


def _load_flatten_function():
    """Lazy-load the Stage 10 `flatten_document_to_pdf_objects` helper."""

    module_path = Path(__file__).resolve().parents[1] / "steps" / "10_arangodb_exporter.py"
    spec = importlib.util.spec_from_file_location("pipeline_stage10", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load Stage 10 module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module.flatten_document_to_pdf_objects  # type: ignore[attr-defined]


@app.command()
def ingest(
    html_path: Path = typer.Argument(..., exists=True, readable=True, help="Path to the source HTML file."),
    output_dir: Path = typer.Option(
        Path("data/results/html_ingest"),
        "--output-dir",
        "-o",
        help="Directory where artifacts (UnifiedDocument, flattened JSON) will be stored.",
    ),
    flatten: bool = typer.Option(
        False,
        "--flatten/--no-flatten",
        help="If set, also run Stage 10 flattening against the generated UnifiedDocument.",
    ),
    skip_embeddings: bool = typer.Option(
        True,
        help="Skip embedding generation when flattening (recommended for local comparison runs).",
    ),
    fast_embeddings: bool = typer.Option(
        True,
        help="Use deterministic hash embeddings when flattening (CI safe).",
    ),
) -> None:
    """Convert an HTML file into the canonical UnifiedDocument (and optional flatten)."""

    provider = HTMLProvider()
    typer.echo(f"Loading HTML document: {html_path}")
    unified_document = provider.extract_document(html_path)

    target_dir = output_dir / html_path.stem
    target_dir.mkdir(parents=True, exist_ok=True)

    unified_path = target_dir / "unified_document.json"
    unified_path.write_text(unified_document.model_dump_json(indent=2))
    typer.echo(f"Saved unified document to {unified_path}")

    if not flatten:
        return

    flatten_document_to_pdf_objects = _load_flatten_function()

    pipeline_payload = {
        "unified_document": unified_document.model_dump(by_alias=True, mode="json"),
        "source_files": {"sections": str(html_path)},
    }

    flattened = flatten_document_to_pdf_objects(
        pipeline_data=pipeline_payload,
        summaries_data={"summaries": []},
        skip_embeddings=skip_embeddings,
        fast_embeddings=fast_embeddings,
    )

    flattened_path = target_dir / "flattened_objects.json"
    flattened_path.write_text(json.dumps(flattened, indent=2))
    typer.echo(f"Saved flattened objects to {flattened_path} (count={len(flattened)})")


@app.command()
def summarize(
    unified_path: Path = typer.Argument(..., exists=True, readable=True, help="Path to a UnifiedDocument JSON."),
) -> None:
    """Quick summary helper for an existing UnifiedDocument file."""

    document = UnifiedDocument.model_validate_json(unified_path.read_text())
    counts = {}
    total_chars = 0
    for block in document.blocks:
        counts[block.type] = counts.get(block.type, 0) + 1
        if isinstance(block.content, str):
            total_chars += len(block.content)

    typer.echo(f"Block counts: {counts}")
    typer.echo(f"Total text characters: {total_chars}")


if __name__ == "__main__":
    app()
