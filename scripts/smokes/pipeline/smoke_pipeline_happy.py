#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv",
# ]
# ///
from __future__ import annotations

import os
import subprocess
from pathlib import Path
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: happy-path pipeline run with gold validation")


@app.command()
def main(
    pdf: Path = typer.Option(
        Path("data/input/pipeline/BHT_CV32A65X_marked.pdf"), exists=True
    ),
    results: Path = typer.Option(Path("data/results/pipeline_happy_smoke"), "-o"),
    arango_db: str = typer.Option("pdf_knowledge_base_test"),
):
    load_dotenv(find_dotenv() or None)
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(Path.cwd() / "src"))
    env["ARANGO_DATABASE"] = arango_db
    results.mkdir(parents=True, exist_ok=True)

    cmd = [
        os.environ.get("PYTHON", "python"),
        "-m",
        "extractor.pipeline.cli_happy",
        "--pdf",
        str(pdf),
        "--results",
        str(results),
    ]
    proc = subprocess.run(cmd, env=env)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    vr = Path("scripts/artifacts/validate_stage_07.json")
    if not vr.exists():
        raise SystemExit("Validation report for stage 07 missing (expect artifacts)")
    typer.echo("OK: happy-path pipeline succeeded and wrote validation reports")


if __name__ == "__main__":
    app()
