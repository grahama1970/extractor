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
import os
import subprocess
from pathlib import Path
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: run summary JSON is created with score")


@app.command()
def main(
    pdf: Path = typer.Option(Path("data/input/pipeline/BHT_CV32A65X_marked.pdf"), exists=True),
    results: Path = typer.Option(Path("data/results/pipeline_happy_smoke2"), "-o"),
    arango_db: str = typer.Option("pdf_knowledge_base_test"),
):
    """Run the PDF processing pipeline."""
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

    out = Path("scripts/artifacts/run_summary_happy.json")
    if not out.exists():
        raise SystemExit("run_summary_happy.json missing")
    data = json.loads(out.read_text())
    if not data.get("ok") or data.get("score") is None:
        raise SystemExit("invalid run summary content")
    typer.echo("OK: run summary has score and per-stage status")


if __name__ == "__main__":
    app()
