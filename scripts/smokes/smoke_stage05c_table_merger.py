#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
from __future__ import annotations

import json
import shutil
from pathlib import Path

import typer

from extractor.pipeline.steps.s05c_table_merger import run as run_table_merger

app = typer.Typer(
    add_completion=False,
    help="Smoke: Stage 05c merges split tables using deterministic heuristics.",
)


def _tables_payload() -> dict:
    """Return table data with indices, bounding box, and structured content."""
    return {
        "tables": [
            {
                "table_index": 1,
                "page_index": 0,
                "bbox": [40, 120, 460, 320],
                "pandas_df": [
                    {"Cycle": "1", "Action": "Read"},
                    {"Cycle": "2", "Action": "Write"},
                ],
                "llm_title": "Branch Table (Part 1)",
            },
            {
                "table_index": 2,
                "page_index": 1,
                "bbox": [45, 80, 465, 280],
                "pandas_df": [
                    {"Cycle": "3", "Action": "Commit"},
                    {"Cycle": "4", "Action": "Flush"},
                ],
                "llm_title": "Branch Table Continued",
            },
        ]
    }


@app.command()
def main(
    results: Path = typer.Option(
        Path("data/results/pipeline/smokes/05c_table_merger"),
        "--results",
        "-o",
        help="Scratch pipeline directory for Stage 05c.",
    )
) -> None:
    """Prepare pipeline results directory for stage 05c."""
    if results.exists():
        shutil.rmtree(results)
    stage_root = results
    stage05_dir = stage_root / "05_table_extractor" / "json_output"
    stage05_dir.mkdir(parents=True, exist_ok=True)
    payload = _tables_payload()
    stage05_dir.joinpath("05_tables.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    stage05b_dir = stage_root / "05b_table_describer" / "json_output"
    stage05b_dir.mkdir(parents=True, exist_ok=True)
    stage05b_dir.joinpath("05b_tables.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    try:
        out_file = run_table_merger(input_dir=stage_root, output_dir=stage_root)
    except Exception as exc:  # pragma: no cover - smoke script
        typer.echo(f"Stage 05c execution failed: {exc}", err=True)
        raise typer.Exit(code=1)

    if not out_file.exists():
        typer.echo("05c_tables.json missing after run", err=True)
        raise typer.Exit(code=2)
    merged = json.loads(out_file.read_text(encoding="utf-8")).get("tables") or []
    if not merged:
        typer.echo("Merged payload is empty", err=True)
        raise typer.Exit(code=3)
    merged_with = sum(1 for tbl in merged if tbl.get("merged_with"))
    if len(merged) > 2 or merged_with == 0:
        typer.echo("Expected at least one merged table but none were marked.", err=True)
        raise typer.Exit(code=4)
    typer.echo("OK: Stage 05c merged split tables and wrote 05c_tables.json.")


if __name__ == "__main__":
    app()
