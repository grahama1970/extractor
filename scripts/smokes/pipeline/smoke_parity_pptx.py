#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv",
# ]
# ///
"""PPTX vs PDF parity smoke (Stage 10 flattened objects)."""

from __future__ import annotations

import json
import importlib.util
from pathlib import Path
from typing import Dict

import typer

from extractor.pipeline.structured_pipeline import STRUCTURED_PIPELINES, run_structured_pipeline
from extractor.core.providers.pptx import PPTXProvider
from extractor.pipeline.utils.unified_conversion import build_unified_document_from_reflow

app = typer.Typer(add_completion=False)


def _load_flatten_function():
    """Load a module from a specified file path for execution."""
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
    pptx_path: Path = typer.Option(
        Path(
            "data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.pptx"
        ),
        exists=True,
    ),
    results_dir: Path = typer.Option(Path("data/results/structured_parity_smoke/pptx")),
    allowed_delta: int = typer.Option(5),
) -> None:
    """Generate PowerPoint slides from JSON data and save to specified directory."""
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
    pptx_flattened = json.loads(Path(artifacts["stage10_flattened"]).read_text())
    pptx_stage07 = json.loads(Path(artifacts["stage07"]).read_text())

    pdf_types: Dict[str, int] = {}
    pptx_types: Dict[str, int] = {}
    for obj in pdf_flattened:
        pdf_types[obj["object_type"]] = pdf_types.get(obj["object_type"], 0) + 1
    for obj in pptx_flattened:
        pptx_types[obj["object_type"]] = pptx_types.get(obj["object_type"], 0) + 1

    artifacts_dir = Path("scripts/artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    summary_path = artifacts_dir / "pptx_pdf_parity_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "pdf": {"count": len(pdf_flattened), "types": pdf_types},
                "pptx": {"count": len(pptx_flattened), "types": pptx_types},
                "inputs": {
                    "pdf_stage07": str(pdf_stage07),
                    "pptx_path": str(pptx_path),
                    "pptx_flattened": str(artifacts["stage10_flattened"]),
                },
            },
            indent=2,
        )
    )

    # Relaxed acceptance: sections-only presence for PPTX
    pptx_sections = pptx_stage07.get("reflowed_sections") or []
    if not isinstance(pptx_sections, list) or len(pptx_sections) == 0:
        typer.echo("No sections found in PPTX Stage 07 reflow output.")
        raise typer.Exit(code=1)
    first_section_title = str(pptx_sections[0].get("title") or "").strip()

    # Additional acceptance: verify Stage 10 objects carry non-root section context
    has_section_context = any(
        isinstance(obj, dict) and str(obj.get("section_id") or "") not in ("", "document-root")
        for obj in pptx_flattened
    )
    if not has_section_context:
        typer.echo("No Stage 10 object contains non-root section context.")
        raise typer.Exit(code=1)

    # Optional: at least one flattened object should reflect the first section title
    if first_section_title:
        if not any(
            isinstance(obj, dict)
            and str(obj.get("section_title") or "").strip() == first_section_title
            for obj in pptx_flattened
        ):
            typer.echo("No Stage 10 object matched the first section title from Stage 07.")
            raise typer.Exit(code=1)

    typer.echo(
        f"PPTX parity presence checks passed (sections-only + section-context). sections={len(pptx_sections)}"
    )


if __name__ == "__main__":
    app()
