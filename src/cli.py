#!/usr/bin/env python3
"""Single-surface extractor CLI (happy path).

Usage (per docs/03_guides/HAPPYPATH_GUIDE.md)
    python -m src.cli extract <input> <out_dir> [--mode fast|accurate] [--prove]

Behavior
  - PDF
      • fast: PyMuPDF text-only, writes ``<out>/<stem>_fast.json``.
      • accurate: runs the function-first pipeline (offline-friendly flags),
        then materializes Stage 10 flattened JSON with deterministic, fast
        embeddings; proving is opt-in.
  - Structured formats (HTML/DOCX/PPTX/XLSX/EPUB/RST/MD/XML/IMG):
      • load via provider, write a UnifiedDocument payload under
        ``<out>/<stem>/07_reflow_section/json_output/07_reflowed.json`` and
        a Stage 10 ``10_flattened_data.json``.

Notes
  - We avoid DB export by passing ``skip_export=True`` to Stage 10 but still
    emit the flattened JSON.
  - Minimal option surface; errors are reported with actionable messages.
"""

from __future__ import annotations

import json
import sys
import subprocess
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Type

import typer
from loguru import logger

from extractor.core.providers.registry import provider_from_filepath
from extractor.core.providers.pdf import PdfProvider
from extractor.fast_extract.pymupdf_fast import extract_fast_text
from extractor.core.schema.unified_document import HierarchyNode

# Stage 10 flatten helper (imported once; can be monkeypatched in tests)
from extractor.pipeline.steps import s10_arangodb_exporter as s10

# Typer app --------------------------------------------------------------


app = typer.Typer(
    name="extractor",
    help="Unified document extractor (fast PDF, accurate PDF, structured formats)",
    add_completion=False,
)


class Mode(str, Enum):
    fast = "fast"
    accurate = "accurate"


# Helpers ----------------------------------------------------------------


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _run_pipeline_accurate(pdf: Path, out_dir: Path, prove: bool) -> None:
    """Invoke the sequential pipeline with offline-friendly toggles.

    We rely on ``extractor.pipeline.run_pipeline`` (function-first) instead of
    the deleted ``run_all`` wrapper. Stage 10 is re-run afterwards with
    deterministic embeddings to guarantee ``10_flattened_data.json`` exists
    even when the pipeline skipped DB export.
    """

    from extractor.pipeline import run_pipeline

    args = [
        "--pdf",
        str(pdf),
        "--out",
        str(out_dir),
        # Keep deterministic/offline toggles but allow summaries and enrichers to run
        "--skip-fig-descriptions",  # no VLM calls in Stage 06
        "--skip-llm03",  # header verifier offline
        # Note: 09a annotator enabled to satisfy audit/visuals
        "--skip-export",  # avoid DB I/O; we'll still flatten
        "--extract-requirements",  # keep 07r deterministic miner on
        "--skip-scillm-preflight",  # offline-friendly
    ]

    if prove:
        args.append("--prove-requirements")

    rc = run_pipeline.main(args)
    if rc != 0:
        raise typer.Exit(code=rc)

    # Ensure summaries exist (Stage 09 is skipped when summary-only=True)
    summaries = out_dir / "09_section_summarizer" / "json_output" / "09_summaries.json"
    if not summaries.exists():
        _ensure_parent(summaries)
        summaries.write_text(json.dumps({"summaries": [], "meta": {"stub": True}}, indent=2))

    # Materialize flattened data deterministically (skip_export=True)
    reflow = out_dir / "07_reflow_section" / "json_output" / "07_reflowed.json"
    if not reflow.exists():
        raise typer.Exit(code=1)

    s10.run(
        reflowed_json=reflow,
        summaries_json=summaries,
        output_dir=out_dir,
        collection_name="pdf_objects",
        skip_export=True,
        skip_embeddings=True,
        fast_embeddings=True,
    )


def _detect_fast_sections(pages: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """Heuristic section hints for fast mode (cheap regex on headings).

    Returns a list of dicts with: title, page (1-based), line_idx, line_text.
    Safe to ignore downstream if noisy.
    """

    import re

    heading_re = re.compile(r"^(?:\d+(?:\.\d+)*\.?\s+.+|[A-Z][A-Z0-9\.]{2,}\s+.+)")

    hints: list[Dict[str, Any]] = []
    for page in pages:
        text = page.get("text") or ""
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue
            if len(line_stripped) > 140:
                continue
            upper_ratio = sum(c.isupper() for c in line_stripped) / max(len(line_stripped), 1)
            if heading_re.match(line_stripped) or upper_ratio > 0.7:
                hints.append(
                    {
                        "title": line_stripped,
                        "page": page.get("page"),
                        "line_idx": idx,
                        "line_text": line_stripped,
                    }
                )
    return hints


def _run_pdf_fast(pdf: Path, out_dir: Path, with_sections: bool) -> Path:
    data = extract_fast_text(str(pdf))
    if with_sections:
        data["fast_sections"] = _detect_fast_sections(data.get("pages", []))
    out_path = out_dir / f"{pdf.stem}_fast.json"
    _ensure_parent(out_path)
    out_path.write_text(json.dumps(data, indent=2))
    return out_path


def _append_walkthrough(pdf: Path, out_dir: Path, mode: str, fast_sections: bool) -> None:
    """Append a short note to walkthrough.md (PDF runs only)."""

    wt = Path("walkthrough.md")
    if not wt.exists():
        try:
            wt.write_text("# Walkthrough\n\n", encoding="utf-8")
        except Exception:
            return

    annotated = out_dir / "09a_pdf_annotator" / "annotated.pdf"
    audit = out_dir / "09b_audit" / "json_output" / "09b_audit.json"
    reflow = out_dir / "07_reflow_section" / "json_output" / "07_reflowed.json"
    flat = out_dir / "10_arangodb_exporter" / "json_output" / "10_flattened_data.json"
    fast = out_dir / f"{pdf.stem}_fast.json"

    lines = [
        "\n## Run note",
        f"- PDF: {pdf}",
        f"- Mode: {mode}"
        + (" (fast-section heuristics)" if fast_sections and mode == "fast" else ""),
        f"- Output dir: {out_dir}",
    ]

    if mode == "fast":
        lines.append(f"- Fast JSON: {fast if fast.exists() else 'n/a'}")
    else:
        lines.append(f"- Reflow: {reflow if reflow.exists() else 'n/a'}")
        lines.append(f"- Flattened: {flat if flat.exists() else 'n/a'}")
        lines.append(f"- Annotated PDF: {annotated if annotated.exists() else 'n/a'}")
        lines.append(f"- Audit: {audit if audit.exists() else 'n/a'}")

    try:
        wt.write_text(wt.read_text() + "\n" + "\n".join(lines) + "\n")
    except Exception:
        # Keep logging best-effort; never fail the run for walkthrough issues
        pass


def _flatten_unified(unified_doc: Dict[str, Any], source: Path, target_root: Path) -> Path:
    """Flatten a UnifiedDocument payload and write Stage 10 JSON."""

    pipeline_payload = {
        "unified_document": unified_doc,
        "source_files": {"sections": str(source)},
    }

    flattened = s10.flatten_document_to_pdf_objects(
        pipeline_data=pipeline_payload,
        summaries_data={"summaries": []},
        skip_embeddings=True,
        fast_embeddings=True,
    )

    flat_path = target_root / "10_arangodb_exporter" / "json_output" / "10_flattened_data.json"
    _ensure_parent(flat_path)
    flat_path.write_text(json.dumps(flattened, indent=2))
    return flat_path


def _run_structured(provider_cls: Type, input_file: Path, out_dir: Path) -> Dict[str, Path]:
    # Most providers accept no positional args; PdfProvider is handled earlier.
    provider = provider_cls()
    unified = provider.extract_document(str(input_file))

    # Ensure a hierarchy exists for downstream consumers; synthesize a root if absent.
    if getattr(unified, "hierarchy", None) is None:
        root = HierarchyNode(id="root", block_id=None, title=input_file.stem, level=1, children=[])
        for block in unified.blocks:
            if getattr(block, "parent_id", None) is None:
                block.parent_id = root.id
        unified.hierarchy = root

    unified_payload = unified.model_dump(by_alias=True, mode="json")

    base = out_dir / input_file.stem
    reflow_path = base / "07_reflow_section" / "json_output" / "07_reflowed.json"
    _ensure_parent(reflow_path)
    reflow_path.write_text(json.dumps({"unified_document": unified_payload}, indent=2))

    flat_path = _flatten_unified(unified_payload, input_file, base)
    return {"reflow": reflow_path, "flattened": flat_path}


# Command ----------------------------------------------------------------


@app.command()
def extract(
    input_file: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False, readable=True, help="Input document"),
    output_dir: Path = typer.Argument(..., help="Output directory for artifacts"),
    mode: Mode = typer.Option(Mode.accurate, "--mode", help="PDF only: fast or accurate"),
    prove: bool = typer.Option(False, "--prove", help="Enable Lean4 proving (accurate PDF only)"),
    fast_sections: bool = typer.Option(
        False,
        "--fast-section",
        "--fast-sections",
        help="Fast PDF only: add heuristic section hints (light heading regex)",
    ),
    log_walkthrough: bool = typer.Option(
        False,
        "--log-walkthrough",
        help="Append a short run note to walkthrough.md (PDF only)",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
):
    """Unified extraction entrypoint (PDF + structured formats)."""

    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    output_dir.mkdir(parents=True, exist_ok=True)

    provider_cls = provider_from_filepath(str(input_file))

    # PDF branch -------------------------------------------------------
    if provider_cls is PdfProvider:
        if mode == Mode.fast:
            out = _run_pdf_fast(input_file, output_dir, with_sections=fast_sections)
            if log_walkthrough:
                _append_walkthrough(pdf=input_file, out_dir=output_dir, mode="fast", fast_sections=fast_sections)
            typer.echo(f"✓ Fast PDF extraction → {out}")
            raise typer.Exit(0)

        if fast_sections:
            typer.echo("[yellow]--fast-section applies only to --mode fast (ignored).[/yellow]")

        typer.echo("Running accurate PDF pipeline (offline-friendly)…")
        _run_pipeline_accurate(input_file, output_dir, prove)
        if log_walkthrough:
            _append_walkthrough(pdf=input_file, out_dir=output_dir, mode="accurate", fast_sections=False)
        typer.echo(f"✓ Accurate PDF extraction → {output_dir}")
        raise typer.Exit(0)

    # Structured branch ------------------------------------------------
    try:
        paths = _run_structured(provider_cls, input_file, output_dir)
        typer.echo("✓ Structured extraction complete")
        for label, path in paths.items():
            typer.echo(f"  {label}: {path}")
    except Exception as e:  # pragma: no cover - surfaced to user
        typer.echo(f"Extraction failed: {e}", err=True)
        raise typer.Exit(1)


# Entrypoint -------------------------------------------------------------


if __name__ == "__main__":
    app()
