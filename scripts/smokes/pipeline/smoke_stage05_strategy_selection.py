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
from typing import List, Dict

import typer
from dotenv import load_dotenv, find_dotenv

app = typer.Typer(add_completion=False, help="Stage 05 strategy selection smoke")

RESULTS_DIR = Path("data/results/pipeline")
TABLE_PATH = Path("05_table_extractor/json_output/05_tables.json")

SANITIZED_TOKENS = ["\n", "  "]


def ensure_stage05_tables(results_root: Path) -> Path:
    root_path = Path(str(results_root))
    target = root_path / TABLE_PATH
    if target.exists():
        return target

    import subprocess

    subprocess.run(
        [
            sys.executable,
            "-m",
            "extractor.pipeline.tools.quick_smoke",
            "--pdf",
            str(Path("data/input/pipeline/BHT_CV32A65X_marked.pdf")),
        ],
        check=True,
    )
    if not target.exists():
        raise SystemExit("Stage 05 tables JSON missing even after quick_smoke")
    return target


def has_split_tokens(row: Dict[str, str]) -> bool:
    values = row.values() if isinstance(row, dict) else row
    return any(any(tok in str(cell) for tok in SANITIZED_TOKENS) for cell in values)


@app.command()
def main(results: Path = typer.Option(Path("data/results/pipeline"), "--results")) -> None:
    load_dotenv(find_dotenv(usecwd=True) or None)
    target = ensure_stage05_tables(results)
    tables = json.loads(target.read_text(encoding="utf-8"))

    issues: List[Dict[str, object]] = []
    sanitized_changes = 0

    for entry in tables.get("tables", []):
        raw_rows = entry.get("pandas_df_raw") or entry.get("pandas_df")
        clean_rows = entry.get("pandas_df")
        frag = entry.get("fragmentation_score")

        if frag not in (0, None):
            issues.append(
                {
                    "page": entry.get("page_number"),
                    "strategy": entry.get("strategy"),
                    "type": "fragmentation",
                    "details": frag,
                }
            )

        if isinstance(raw_rows, list) and isinstance(clean_rows, list):
            for raw, clean in zip(raw_rows, clean_rows):
                if has_split_tokens(clean):
                    issues.append(
                        {
                            "page": entry.get("page_number"),
                            "strategy": entry.get("strategy"),
                            "type": "sanitized_contains_tokens",
                            "details": clean,
                        }
                    )
                if raw != clean:
                    sanitized_changes += 1
        else:
            issues.append(
                {
                    "page": entry.get("page_number"),
                    "strategy": entry.get("strategy"),
                    "type": "unexpected_row_format",
                    "details": {
                        "raw_type": type(raw_rows).__name__,
                        "clean_type": type(clean_rows).__name__,
                    },
                }
            )

    art_dir = Path("scripts/artifacts")
    art_dir.mkdir(parents=True, exist_ok=True)
    (art_dir / "stage05_strategy_selection.json").write_text(
        json.dumps(
            {"issues": issues, "sanitized_changes": sanitized_changes}, ensure_ascii=False, indent=2
        )
    )

    if issues:
        raise SystemExit(
            "Stage 05 strategy selection smoke failed; see stage05_strategy_selection.json"
        )

    if sanitized_changes == 0:
        typer.echo("WARN: No differences between raw and sanitized tables detected.")
    else:
        typer.echo(f"OK: Sanitized {sanitized_changes} rows without split tokens.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        app()
    else:
        main()
