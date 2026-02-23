#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "openpyxl>=3.1",
# ]
# ///
"""Spreadsheet: multi-sheet workbook yields tables with distinct sheet names in Stage 10."""

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
    xlsx_path = tmp_dir / "multisheet.xlsx"
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "S1"
    ws1.append(["A", "B"])
    ws1.append([1, 2])
    ws2 = wb.create_sheet(title="S2")
    ws2.append(["C", "D"])
    ws2.append([3, 4])
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
    flat = json.loads(Path(artifacts["stage10_flattened"]).read_text())
    sheets = set()
    for obj in flat:
        if obj.get("object_type") == "Table":
            md = (obj.get("data") or {}).get("metadata") or {}
            attr = md.get("attributes") or {}
            s = attr.get("sheet")
            if s:
                sheets.add(s)
    if len(sheets) < 2:
        typer.echo(f"Expected 2 distinct sheet names in Stage 10 tables; got {sheets}", err=True)
        raise typer.Exit(code=1)
    typer.echo("Spreadsheet multi-sheet context passed.")


if __name__ == "__main__":
    app()
