#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "openpyxl>=3.1",
# ]
# ///
"""Spreadsheet: first-row header detection propagates into Stage 07 table.headers."""

from __future__ import annotations

import json
from pathlib import Path
import typer
from openpyxl import Workbook

from extractor.pipeline.structured_pipeline import STRUCTURED_PIPELINES, run_structured_pipeline
from extractor.core.providers.spreadsheet import SpreadsheetProvider

app = typer.Typer(add_completion=False)


@app.command()
def main(
    tmp_dir: Path = typer.Option(Path("data/results/structured_parity_smoke/spreadsheet_synth")),
):
    tmp_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = tmp_dir / "headers.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["A", "B", "C"])  # header row
    ws.append([1, 2, 3])
    wb.save(xlsx_path)

    meta = STRUCTURED_PIPELINES[SpreadsheetProvider]
    artifacts = run_structured_pipeline(
        SpreadsheetProvider,
        xlsx_path,
        tmp_dir,
        stage_prefix=meta.stage_prefix,
        skip_export10=True,
        skip_embeddings10=True,
        fast_embeddings10=True,
    )
    s07 = json.loads(Path(artifacts["stage07"]).read_text())
    sections = s07.get("reflowed_sections") or []
    if not sections:
        typer.echo("No sections in Spreadsheet Stage 07.", err=True)
        raise typer.Exit(code=1)
    tables = sections[0].get("tables") or []
    if not tables:
        typer.echo("No tables in Spreadsheet Stage 07.", err=True)
        raise typer.Exit(code=1)
    headers = tables[0].get("headers") or []
    if 0 not in headers:
        typer.echo(f"Expected header row 0 in Stage 07, got {headers}", err=True)
        raise typer.Exit(code=1)
    typer.echo("Spreadsheet header row captured in Stage 07.")


if __name__ == "__main__":
    app()
