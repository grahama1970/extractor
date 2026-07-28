#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "typer>=0.12",
# ]
# ///
from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv, find_dotenv

app = typer.Typer(add_completion=False, help="Stage 05 strategy quality smoke")

RESULTS_DIR = Path("data/results/pipeline")
TABLE_JSON = Path("05_table_extractor/json_output/05_tables.json")


def ensure_stage05(results_root: Path) -> Path:
    """Ensure Stage 05 JSON exists by running pipeline if missing."""
    target = results_root / TABLE_JSON
    if target.exists():
        return target
    from extractor.pipeline.tools.quick_smoke import run as quick_run  # type: ignore

    quick_run.callback(pdf=Path("data/input/pipeline/BHT_CV32A65X_marked.pdf"))  # type: ignore
    if not target.exists():
        raise SystemExit("Stage 05 tables JSON missing even after quick_smoke")
    return target


def detect_fragmentation(entry: dict, columns: list[str]) -> list[dict[str, str]]:
    """Detect fragmentation issues in specified columns of a DataFrame."""
    issues = []
    df = entry.get("pandas_df") or []
    for row_idx, row in enumerate(df):
        for col in columns:
            val = str(row.get(col, ""))
            if "\n" in val or "  " in val or "in in " in val:
                issues.append(
                    {
                        "row": row_idx,
                        "column": col,
                        "value": val,
                    }
                )
    return issues


def run_smoke(results: Path) -> None:
    """Detect fragmentation issues in table data from results."""
    load_dotenv(find_dotenv(usecwd=True) or None)
    table_path = ensure_stage05(results)
    tables_data = json.loads(table_path.read_text(encoding="utf-8"))

    detections = []
    for entry in tables_data.get("tables", []):
        columns = entry.get("pandas_metrics", {}).get("columns", [])
        issues = detect_fragmentation(entry, columns)
        if issues:
            detections.append(
                {
                    "page": entry.get("page_number"),
                    "strategy": entry.get("strategy"),
                    "issues": issues,
                }
            )

    fallback_metrics = (tables_data.get("metrics") or {}).get("quality_fallback", {})

    art_dir = Path("scripts/artifacts")
    art_dir.mkdir(parents=True, exist_ok=True)
    artifact_payload = {
        "detections": detections,
        "quality_fallback": fallback_metrics,
    }
    (art_dir / "stage05_strategy_quality.json").write_text(
        json.dumps(artifact_payload, ensure_ascii=False, indent=2)
    )
    if detections:
        typer.echo("WARN: Detected fragmentation tokens; see stage05_strategy_quality.json")
    elif fallback_metrics.get("pages_with_fallback"):
        typer.echo(
            "OK: No fragmentation tokens; fallback engaged on "
            f"{fallback_metrics.get('pages_with_fallback')} page(s)."
        )
    else:
        typer.echo("OK: No obvious fragmentation tokens detected")


@app.command()
def main(results: Path = typer.Option(Path("data/results/pipeline"), "--results")) -> None:
    """Run the smoke test using the specified results path."""
    run_smoke(results)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        app()
    else:
        run_smoke(Path("data/results/pipeline"))
