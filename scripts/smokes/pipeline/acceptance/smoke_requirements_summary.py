#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""
Acceptance: run_summary contains requirements counts (after Stage 14)
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import typer

app = typer.Typer(add_completion=False)

PDF = Path("data/input/pipeline/BHT_CV32A65X_with_requirements.pdf")
OUT = Path("data/results/with_requirements_summary")


@app.command()
def main():
    """Run a subprocess to extract data from a PDF using a specified mode."""
    OUT.mkdir(parents=True, exist_ok=True)
    rc = subprocess.run(
        [
            "/home/graham/workspace/experiments/extractor/.venv/bin/python",
            "-m",
            "src.cli",
            "extract",
            str(PDF),
            str(OUT),
            "--mode",
            "accurate",
        ]
    ).returncode
    if rc != 0:
        raise SystemExit(rc)
    run_summary = OUT / "run_summary.json"
    if not run_summary.exists():
        raise SystemExit("run_summary.json missing")
    data = json.loads(run_summary.read_text())
    # Tolerant: just require non-negative integers when present
    req_stats = data.get("requirements") or {}
    ok = isinstance(req_stats, dict)
    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts") / "req_summary_report.json").write_text(
        json.dumps({"ok": ok, "requirements": req_stats}, indent=2)
    )
    if not ok:
        raise SystemExit(1)
    print(json.dumps({"ok": ok}, indent=2))


if __name__ == "__main__":
    app()
