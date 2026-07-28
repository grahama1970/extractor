#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv",
# ]
# ///
"""EPUB vs PDF parity smoke (Stage 10)."""

from __future__ import annotations

import json
import importlib.util
from pathlib import Path
from typing import Dict

import typer

from extractor.pipeline.structured_pipeline import STRUCTURED_PIPELINES, run_structured_pipeline
from extractor.core.providers.epub import EPUBProvider
from extractor.pipeline.utils.unified_conversion import build_unified_document_from_reflow

app = typer.Typer(add_completion=False)


def _load_flatten_function():
    """Load and return a flatten function from a specified module path."""
    module_path = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "extractor"
        / "pipeline"
        / "steps"
        / "10_arangodb_exporter.py"
    )
    spec = importlib.util.spec_from_file_location("pipeline_stage10", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load Stage 10 module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module.flatten_document_to_pdf_objects  # type: ignore[attr-defined]


@app.command()
def main(
    pdf_stage07: Path = typer.Option(
        Path("data/results/pipeline/07_reflow_section/json_output/07_reflowed.json"), exists=True
    ),
    epub_path: Path = typer.Option(
        Path(
            "data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.epub"
        ),
        exists=True,
    ),
    results_dir: Path = typer.Option(Path("data/results/structured_parity_smoke/epub")),
    allowed_delta: int = typer.Option(5),
) -> None:
    """Generate EPUB from PDF data and save results to specified directory."""
    flatten = _load_flatten_function()
    payload = json.loads(pdf_stage07.read_text())
    pdf_unified = build_unified_document_from_reflow(
        sections=payload.get("reflowed_sections") or [],
        source_path=str(payload.get("source_files", {}).get("sections", "unknown.pdf")),
        source_type="pdf",
        document_metadata={"source_files": payload.get("source_files", {})},
    )
    pdf_flattened = flatten(
        pipeline_data={
            "unified_document": pdf_unified.model_dump(by_alias=True, mode="json"),
            "source_files": payload.get("source_files", {}),
        },
        summaries_data={"summaries": []},
        skip_embeddings=True,
        fast_embeddings=True,
    )

    meta = STRUCTURED_PIPELINES[EPUBProvider]
    artifacts = run_structured_pipeline(
        EPUBProvider,
        epub_path,
        results_dir,
        stage_prefix=meta.stage_prefix,
        skip_export10=True,
        skip_embeddings10=True,
        fast_embeddings10=True,
    )
    epub_flattened = json.loads(Path(artifacts["stage10_flattened"]).read_text())

    pdf_types: Dict[str, int] = {}
    e_types: Dict[str, int] = {}
    for obj in pdf_flattened:
        pdf_types[obj["object_type"]] = pdf_types.get(obj["object_type"], 0) + 1
    for obj in epub_flattened:
        e_types[obj["object_type"]] = e_types.get(obj["object_type"], 0) + 1

    artifacts_dir = Path("scripts/artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    summary_path = artifacts_dir / "epub_pdf_parity_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "pdf": {"count": len(pdf_flattened), "types": pdf_types},
                "epub": {"count": len(epub_flattened), "types": e_types},
                "inputs": {
                    "pdf_stage07": str(pdf_stage07),
                    "epub_path": str(epub_path),
                    "epub_flattened": str(artifacts["stage10_flattened"]),
                },
            },
            indent=2,
        )
    )

    # Sections presence + section-context checks for EPUB parity
    pdf_sections = payload.get("reflowed_sections") or []
    try:
        s07 = json.loads(Path(artifacts["stage07"]).read_text())
        epub_sections = s07.get("reflowed_sections") or []
    except Exception:
        epub_sections = []
    if pdf_sections and not epub_sections:
        raise typer.Exit(code=1)
    first_section_title = str(
        (epub_sections[0] or {}).get("title") if epub_sections else ""
    ).strip()
    has_section_context = any(
        isinstance(obj, dict) and str(obj.get("section_id") or "") not in ("", "document-root")
        for obj in epub_flattened
    )
    if not has_section_context:
        typer.echo("No Stage 10 object contains non-root section context (EPUB).", err=True)
        raise typer.Exit(code=1)
    if first_section_title:
        if not any(
            isinstance(obj, dict)
            and str(obj.get("section_title") or "").strip() == first_section_title
            for obj in epub_flattened
        ):
            typer.echo(
                "No Stage 10 object matched the first section title from Stage 07 (EPUB).", err=True
            )
            raise typer.Exit(code=1)
    typer.echo("EPUB parity section + section-context checks passed.")


if __name__ == "__main__":
    app()
