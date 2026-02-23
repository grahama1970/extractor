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


app = typer.Typer(add_completion=False, help="Smoke: run_all offline path")


@app.command()
def main(
    pdf: Path = typer.Option(Path("data/input/pipeline/BHT_CV32A65X_marked.pdf"), exists=True),
    results: Path = typer.Option(Path("data/results/pipeline_smoke_offline"), "-o"),
):
    load_dotenv(find_dotenv() or None)
    cmd = [
        os.environ.get("PYTHON", "python"),
        "-m",
        "extractor.pipeline.run_all",
        "run",
        "--pdf",
        str(pdf),
        "--results",
        str(results),
        "--skip-llm03",
        "--skip-descriptions06",
        "--summary-only07",
        "--skip-proving08",
        "--skip-export10",
        "--skip-embeddings10",
        "--skip-graph11",
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(Path.cwd() / "src"))
    proc = subprocess.run(cmd, env=env)
    raise SystemExit(proc.returncode)


if __name__ == "__main__":
    app()
