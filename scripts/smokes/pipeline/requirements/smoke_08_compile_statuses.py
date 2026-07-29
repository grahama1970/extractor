#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv>=1.0.0,<2",
# ]
# ///
"""
Smoke: Stage 08 compile statuses (offline/deterministic path)
Runs the pipeline with --prove to ensure 08_requirements_enriched.json is present.
Writes scripts/artifacts/req_compile_status.json with counts by status.
"""
from __future__ import annotations
import sys

import json
from pathlib import Path
import subprocess
import typer

app = typer.Typer(add_completion=False)

PDF = Path("data/input/pipeline/BHT_CV32A65X_with_requirements.pdf")
OUT = Path("data/results/with_requirements_prove")


@app.command()
def main():
    """Run the extractor CLI to process PDF and generate enriched JSON output."""
    OUT.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "src.cli",
        "extract",
        str(PDF),
        str(OUT),
        "--mode",
        "accurate",
        "--prove",
    ]
    # Even if proving is skipped by offline guards, run_all synthesizes enriched JSON
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        raise SystemExit(rc)
    enr = OUT / "08_lean4_theorem_prover/json_output/08_requirements_enriched.json"
    if not enr.exists():
        raise SystemExit("08_requirements_enriched.json missing")
    data = json.loads(enr.read_text())
    by_status = {}
    for r in data.get("requirements") or []:
        s = str(r.get("status") or "unknown")
        by_status[s] = by_status.get(s, 0) + 1
    report = {"by_status": by_status, "total": sum(by_status.values())}
    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts") / "req_compile_status.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    app()
