#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv>=1.0.0,<2",
# ]
# ///
"""
Smoke: Stage 07½ Requirements Miner — sentence-level detection
Runs the accurate pipeline for the BHT fixture (miner auto-runs) and asserts >=1 requirement.
Writes scripts/artifacts/req_miner_sentences.json
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import typer

app = typer.Typer(add_completion=False)

PDF = Path("data/input/pipeline/BHT_CV32A65X_with_requirements.pdf")
OUT = Path("data/results/with_requirements_miner")


def ensure_pipeline() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    req_json = OUT / "07_requirements_miner/json_output/07_requirements.json"
    if req_json.exists():
        return req_json
    cmd = [
        "/home/graham/workspace/experiments/extractor/.venv/bin/python",
        "-m",
        "src.cli",
        "extract",
        str(PDF),
        str(OUT),
        "--mode",
        "accurate",
    ]
    if subprocess.run(cmd).returncode != 0:
        raise SystemExit("pipeline extract failed")
    return req_json


@app.command()
def main():
    req_json = ensure_pipeline()
    data = json.loads(req_json.read_text())
    reqs = data.get("requirements") or []
    report = {"total": len(reqs)}
    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts") / "req_miner_sentences.json").write_text(
        json.dumps(report, indent=2)
    )
    if len(reqs) < 1:
        raise SystemExit(1)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    app()
