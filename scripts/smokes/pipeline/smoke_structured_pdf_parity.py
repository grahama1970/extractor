#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv",
# ]
# ///
"""Compare Stage 10 flattened outputs for PDF vs structured format."""

from __future__ import annotations

import json
import importlib.util
from pathlib import Path
from typing import Dict

import typer

from extractor.pipeline.structured_pipeline import (
    FORMAT_TO_PROVIDER,
    STRUCTURED_PIPELINES,
    run_structured_pipeline,
)
from extractor.pipeline.utils.unified_conversion import build_unified_document_from_reflow

app = typer.Typer(add_completion=False)


def _load_flatten_function():
    module_path = Path(__file__).resolve().parents[3] / "src" / "extractor" / "pipeline" / "steps" / "10_arangodb_exporter.py"
    spec = importlib.util.spec_from_file_location("pipeline_stage10", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load Stage 10 module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module.flatten_document_to_pdf_objects  # type: ignore[attr-defined]


@app.command()
def main(
    pdf_stage07: Path = typer.Argument(
        ..., exists=True, readable=True, help="Stage 07 reflowed JSON produced from the PDF pipeline"
    ),
    structured_path: Path = typer.Argument(
        ..., exists=True, readable=True, help="Structured rendition of the same document"
    ),
    format_name: str = typer.Option(
        "html",
        "--format",
        "-f",
        help="Structured format identifier (html, docx, pptx, spreadsheet, epub, rst, xml)",
    ),
    results_dir: Path = typer.Option(
        Path("data/results/structured_parity_smoke"),
        "--results-dir",
        "-o",
        help="Directory to store structured pipeline artifacts",
    ),
    allowed_delta: int = typer.Option(
        5,
        help="Maximum allowed difference in flattened object counts before failing",
    ),
) -> None:
    """Compare flattened Stage 10 objects between PDF and a structured format."""

    format_name = format_name.lower()
    if format_name not in FORMAT_TO_PROVIDER:
        typer.echo(
            f"Unsupported format '{format_name}'. Available: {sorted(FORMAT_TO_PROVIDER.keys())}",
            err=True,
        )
        raise typer.Exit(code=1)

    pdf_payload = json.loads(pdf_stage07.read_text())
    pdf_sections = pdf_payload.get("reflowed_sections", [])
    if not pdf_sections:
        typer.echo("PDF Stage 07 payload missing sections", err=True)
        raise typer.Exit(code=1)

    pdf_unified = build_unified_document_from_reflow(
        sections=pdf_sections,
        source_path=str(pdf_payload.get("source_files", {}).get("sections", "unknown.pdf")),
        source_type="pdf",
        document_metadata={"source_files": pdf_payload.get("source_files", {})},
    )

    flatten = _load_flatten_function()

    pdf_flattened = flatten(
        pipeline_data={
            "unified_document": pdf_unified.model_dump(by_alias=True, mode="json"),
            "source_files": pdf_payload.get("source_files", {}),
        },
        summaries_data={"summaries": []},
        skip_embeddings=True,
        fast_embeddings=True,
    )

    provider_cls = FORMAT_TO_PROVIDER[format_name]
    meta = STRUCTURED_PIPELINES[provider_cls]

    artifacts_dir = Path("scripts/artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    target_results_dir = results_dir / format_name
    artifacts = run_structured_pipeline(
        provider_cls,
        structured_path,
        target_results_dir,
        stage_prefix=meta.stage_prefix,
        skip_export10=True,
        skip_embeddings10=True,
        fast_embeddings10=True,
    )

    structured_flattened = json.loads(Path(artifacts["stage10_flattened"]).read_text())

    pdf_types: Dict[str, int] = {}
    structured_types: Dict[str, int] = {}
    for obj in pdf_flattened:
        pdf_types[obj["object_type"]] = pdf_types.get(obj["object_type"], 0) + 1
    for obj in structured_flattened:
        structured_types[obj["object_type"]] = structured_types.get(obj["object_type"], 0) + 1

    summary_path = artifacts_dir / f"{format_name}_pdf_parity_summary.json"
    summary_payload = {
        "format": format_name,
        "pdf": {"count": len(pdf_flattened), "types": pdf_types},
        "structured": {"count": len(structured_flattened), "types": structured_types},
        "inputs": {
            "pdf_stage07": str(pdf_stage07),
            "structured_path": str(structured_path),
            "structured_flattened": str(artifacts["stage10_flattened"]),
        },
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2))

    typer.echo(f"PDF objects: {len(pdf_flattened)} -> {pdf_types}")
    typer.echo(
        f"{format_name.upper()} objects: {len(structured_flattened)} -> {structured_types}"
    )
    typer.echo(f"Summary written to {summary_path}")

    diff = abs(len(pdf_flattened) - len(structured_flattened))
    if diff > allowed_delta:
        typer.echo(
            f"Parity check failed: object count delta {diff} exceeds allowed {allowed_delta}",
            err=True,
        )
        raise typer.Exit(code=1)

    typer.echo("Parity check passed within allowed delta.")


if __name__ == "__main__":
    app()
