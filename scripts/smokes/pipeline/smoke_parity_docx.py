#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv",
# ]
# ///
"""DOCX vs PDF parity smoke (Stage 10 flattened objects).

Defaults target the BHT sample. Paths can be overridden via CLI.
"""

from __future__ import annotations

import json
import importlib.util
from pathlib import Path
from typing import Dict

import typer

from extractor.pipeline.structured_pipeline import (
    STRUCTURED_PIPELINES,
    run_structured_pipeline,
)
from extractor.core.providers.docx import DOCXProvider
from extractor.pipeline.utils.unified_conversion import build_unified_document_from_reflow

app = typer.Typer(add_completion=False)


def _load_flatten_function():
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
        Path("data/results/pipeline/07_reflow_section/json_output/07_reflowed.json"),
        exists=True,
        readable=True,
        help="PDF Stage 07 reflowed JSON",
    ),
    docx_path: Path = typer.Option(
        Path(
            "data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.docx"
        ),
        exists=True,
        readable=True,
        help="DOCX rendition of the document",
    ),
    results_dir: Path = typer.Option(
        Path("data/results/structured_parity_smoke/docx"),
        file_okay=False,
        dir_okay=True,
        help="Where to write structured pipeline artifacts",
    ),
    allowed_delta: int = typer.Option(5, help="Max allowed delta in object counts"),
) -> None:
    flatten = _load_flatten_function()

    payload = json.loads(pdf_stage07.read_text())
    sections = payload.get("reflowed_sections") or []
    pdf_unified = build_unified_document_from_reflow(
        sections=sections,
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
    docx_flattened = json.loads(Path(artifacts["stage10_flattened"]).read_text())

    pdf_types: Dict[str, int] = {}
    docx_types: Dict[str, int] = {}
    for obj in pdf_flattened:
        pdf_types[obj["object_type"]] = pdf_types.get(obj["object_type"], 0) + 1
    for obj in docx_flattened:
        docx_types[obj["object_type"]] = docx_types.get(obj["object_type"], 0) + 1

    artifacts_dir = Path("scripts/artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    summary_path = artifacts_dir / "docx_pdf_parity_summary.json"
    summary_payload = {
        "pdf": {"count": len(pdf_flattened), "types": pdf_types},
        "docx": {"count": len(docx_flattened), "types": docx_types},
        "inputs": {
            "pdf_stage07": str(pdf_stage07),
            "docx_path": str(docx_path),
            "docx_flattened": str(artifacts["stage10_flattened"]),
        },
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2))
    typer.echo(f"PDF objects: {len(pdf_flattened)} -> {pdf_types}")
    typer.echo(f"DOCX objects: {len(docx_flattened)} -> {docx_types}")
    typer.echo(f"Summary written to {summary_path}")

    # Presence checks per acceptance
    pdf_has_table = any(o["object_type"] == "Table" for o in pdf_flattened)
    docx_has_table = any(o["object_type"] == "Table" for o in docx_flattened)
    pdf_has_figure = any(o["object_type"] == "Figure" for o in pdf_flattened)
    docx_has_figure = any(o["object_type"] == "Figure" for o in docx_flattened)

    # Read structured Stage 07 for diagnostics/presence
    pdf_sections = payload.get("reflowed_sections") or []
    try:
        s07 = json.loads(Path(artifacts["stage07"]).read_text())
        docx_sections = s07.get("reflowed_sections") or []
        diags = s07.get("diagnostics") or []
    except Exception:
        docx_sections = []
        diags = []
    mangled_flag = False
    for d in diags:
        if (
            isinstance(d, dict)
            and d.get("structured_pipeline") == "docx_mangled_check"
            and d.get("mangled_docx")
        ):
            mangled_flag = True
            break

    # Presence rules (skip table requirement if mangled was detected)
    if not mangled_flag and pdf_has_table and not docx_has_table:
        typer.echo("Missing Table in DOCX parity.", err=True)
        raise typer.Exit(code=1)
    if pdf_has_figure and not docx_has_figure:
        typer.echo("Missing Figure in DOCX parity.", err=True)
        raise typer.Exit(code=1)
    if pdf_sections and not docx_sections:
        typer.echo("Missing sections in DOCX parity.", err=True)
        raise typer.Exit(code=1)
    # Section-context checks in Stage 10
    str(
        (docx_sections[0] or {}).get("title") if docx_sections else ""
    ).strip()
    all_section_titles = [str((s or {}).get("title") or "").strip() for s in docx_sections]
    has_section_context = any(
        isinstance(obj, dict) and str(obj.get("section_id") or "") not in ("", "document-root")
        for obj in docx_flattened
    )
    if not has_section_context:
        typer.echo("No Stage 10 object contains non-root section context (DOCX).", err=True)
        raise typer.Exit(code=1)
    # Allow any Stage 07 title to appear in Stage 10 section_title
    present_titles = set(
        str(obj.get("section_title") or "").strip()
        for obj in docx_flattened
        if isinstance(obj, dict)
    )
    if all_section_titles:
        if not any(t for t in all_section_titles if t and t in present_titles):
            typer.echo(
                "No Stage 10 object matched any section title from Stage 07 (DOCX).", err=True
            )
            raise typer.Exit(code=1)

    typer.echo("DOCX parity presence + section-context checks passed.")


if __name__ == "__main__":
    app()
