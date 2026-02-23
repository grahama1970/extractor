#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv",
# ]
# ///
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
import subprocess
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(
    add_completion=False, help="Smoke: happy path with external annotations (skip Stage 01)"
)


@app.command()
def main(
    pdf: Path = typer.Option(Path("data/input/pipeline/BHT_CV32A65X_marked.pdf"), exists=True),
    results: Path = typer.Option(Path("data/results/pipeline_happy_skip01"), "-o"),
):
    load_dotenv(find_dotenv() or None)
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(Path.cwd() / "src"))
    results.mkdir(parents=True, exist_ok=True)

    # Create a tiny valid annotations JSON (normalized around the known table area)
    stage01 = results / "01_annotation_processor" / "json_output"
    stage01.mkdir(parents=True, exist_ok=True)
    anns = {
        "timestamp": "",
        "source_pdf": str(pdf),
        "status": "Completed",
        "annotation_count": 1,
        "annotations": [
            {
                "id": "ui-0001",
                "page": 0,
                "type": "table_region",
                "original_rect": [100.0, 200.0, 500.0, 500.0],
                "expanded_rect": [80.0, 180.0, 520.0, 520.0],
            }
        ],
    }
    anno_path = stage01 / "01_annotations.json"
    anno_path.write_text(json.dumps(anns, indent=2))
    clean_pdf = results / "01_annotation_processor" / f"{pdf.stem}_clean.pdf"
    shutil.copyfile(str(pdf), str(clean_pdf))

    cmd = [
        env.get("PYTHON", "python"),
        "-m",
        "extractor.pipeline.run_all",
        "--pdf",
        str(pdf),
        "--results",
        str(results),
        "--annotations-json",
        str(anno_path),
        "--clean-pdf",
        str(clean_pdf),
        "--validate",
        "--skip-llm03",
        "--skip-descriptions06",
        "--summary-only07",
        "--skip-proving08",
        "--fast-embeddings10",
    ]
    proc = subprocess.run(cmd, env=env)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    out = Path("scripts/artifacts/validate_stage_07.json")
    if not out.exists():
        raise SystemExit("Validation artifact missing")
    typer.echo("OK: skip-01 happy path ran with external annotations")


if __name__ == "__main__":
    app()
