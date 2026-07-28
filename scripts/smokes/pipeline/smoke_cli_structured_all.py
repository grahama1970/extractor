#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""CLI smoke: extract all structured formats and assert Stage 07/10 exist.

Formats covered: HTML, DOCX, PPTX, XLSX, EPUB, RST, XML, MD
"""

from __future__ import annotations

import subprocess
from pathlib import Path
import json
import sys
import typer

app = typer.Typer(add_completion=False)


FORMAT_SAMPLES = [
    (
        "html",
        Path("data/results/pipeline/01_annotation_processor/BHT_CV32A65X_marked_clean.html"),
        "07_html_ingest",
    ),
    (
        "docx",
        Path(
            "data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.docx"
        ),
        "07_docx_ingest",
    ),
    (
        "pptx",
        Path(
            "data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.pptx"
        ),
        "07_pptx_ingest",
    ),
    (
        "xlsx",
        Path(
            "data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.xlsx"
        ),
        "07_spreadsheet_ingest",
    ),
    (
        "epub",
        Path(
            "data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.epub"
        ),
        "07_epub_ingest",
    ),
    (
        "rst",
        Path(
            "data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.rst"
        ),
        "07_rst_ingest",
    ),
    (
        "xml",
        Path(
            "data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.xml"
        ),
        "07_xml_ingest",
    ),
    (
        "md",
        Path(
            "data/results/pipeline/01_annotation_processor/bht_formats/BHT_CV32A65X_marked_clean.md"
        ),
        "07_markdown_ingest",
    ),
]


def _assert_stage_paths(root: Path, stem: str, stage07_dir: str) -> None:
    """Assert existence of stage output paths for a given stem."""
    s07 = root / stem / stage07_dir / "json_output" / "07_reflowed.json"
    s10 = root / stem / "10_arangodb_exporter" / "json_output" / "10_flattened_data.json"
    if not s07.exists() or not s10.exists():
        raise AssertionError(f"Missing Stage outputs for {stem}: {s07} or {s10}")
    # sanity parse
    json.loads(s07.read_text())
    json.loads(s10.read_text())


@app.command()
def main(
    out_root: Path = typer.Option(Path("data/results/cli_smokes/structured_all")),
):
    """Process and organize sample data into structured output directories."""
    out_root.mkdir(parents=True, exist_ok=True)
    for label, sample, stage07_dir in FORMAT_SAMPLES:
        if not sample.exists():
            typer.echo(f"[skip] Sample not found for {label}: {sample}")
            continue
        out_dir = out_root / label
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, "-m", "src.cli", "extract", str(sample), str(out_dir)]
        proc = subprocess.run(cmd)
        if proc.returncode != 0:
            typer.echo(f"CLI structured extract failed for {label}.", err=True)
            raise typer.Exit(code=1)
        _assert_stage_paths(out_dir, sample.stem, stage07_dir)
        typer.echo(f"[ok] {label} → Stage 07/10 present.")
    typer.echo("CLI structured all-formats smoke passed.")


if __name__ == "__main__":
    app()
