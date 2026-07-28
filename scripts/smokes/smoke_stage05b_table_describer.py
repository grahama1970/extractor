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

from extractor.pipeline.steps.s05b_table_describer import run as run_table_describer

app = typer.Typer(
    add_completion=False,
    help="Smoke: Stage 05b table describer copies tables under --skip-descriptions.",
)


def _write_stage05_tables(path: Path) -> None:
    """Write stage 05 table data to path as JSON."""
    path.write_text(
        json.dumps(
            {
                "tables": [
                    {
                        "table_index": 1,
                        "page_index": 0,
                        "bbox": [20, 80, 420, 200],
                        "rows": 2,
                        "columns": 2,
                        "title": "INFERRED: Cache Behavior Table",
                        "pandas_df": [
                            {"Mode": "Strong", "Latency": "1"},
                            {"Mode": "Relaxed", "Latency": "2"},
                        ],
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )


@app.command()
def main(
    results: Path = typer.Option(
        Path("data/results/pipeline/smokes/05b_table_describer"),
        "--results",
        "-o",
        help="Scratch pipeline directory for Stage 05b sanity.",
    )
) -> None:
    """Remove the specified results directory if it exists."""
    if results.exists():
        shutil.rmtree(results)
    stage05_json = results / "05_table_extractor" / "json_output"
    stage05_json.mkdir(parents=True, exist_ok=True)
    _write_stage05_tables(stage05_json / "05_tables.json")

    try:
        run_table_describer(
            stage_05_dir=results / "05_table_extractor", output_dir=results, skip_descriptions=True
        )
    except Exception as exc:  # pragma: no cover - smoke script
        typer.echo(f"Stage 05b execution failed: {exc}", err=True)
        raise typer.Exit(code=1)

    target = results / "05b_table_describer" / "json_output" / "05b_tables.json"
    if not target.exists():
        typer.echo("05b_tables.json missing after run", err=True)
        raise typer.Exit(code=2)
    payload = json.loads(target.read_text(encoding="utf-8"))
    tables = payload.get("tables") or []
    if not tables:
        typer.echo("No tables copied into 05b output", err=True)
        raise typer.Exit(code=3)
    typer.echo("OK: Stage 05b produced 05b_tables.json in skip mode.")


if __name__ == "__main__":
    app()
