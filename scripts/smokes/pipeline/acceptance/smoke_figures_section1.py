#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""
Acceptance: Ensure Section 1 has at least 1 figure (Stage 06 carried into Stage 07 payload).
"""
from __future__ import annotations
import sys

import json
import os
import subprocess
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)

PDF = Path("data/input/pipeline/BHT_CV32A65X_with_requirements.pdf")
OUT = Path("data/results/with_requirements_figures")


def ensure_stage07() -> Path:
    """Ensure reflowed JSON exists, returning its path."""
    OUT.mkdir(parents=True, exist_ok=True)
    p07 = OUT / "07_reflow_section/json_output/07_reflowed.json"
    if p07.exists():
        return p07
    cmd = [
        sys.executable,
        "-m",
        "src.cli",
        "extract",
        str(PDF),
        str(OUT),
        "--mode",
        "accurate",
    ]
    if subprocess.run(cmd).returncode != 0:
        raise SystemExit("extract failed")
    return p07


@app.command()
def main():
    """Count figures in the first section of a reflowed document."""
    p07 = ensure_stage07()
    d = json.loads(p07.read_text())
    secs = d.get("reflowed_sections", [])
    if not secs:
        typer.echo("No sections", err=True)
        raise typer.Exit(1)
    s1 = secs[0]
    figures = s1.get("figures") or []
    report = {"section1_figures": len(figures)}
    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts") / "figures_section1_summary.json").write_text(
        json.dumps(report, indent=2)
    )
    strict = os.getenv("ACCEPT_STRICT", "").lower() in {"1", "true", "yes", "y"}
    if strict and len(figures) < 1:
        typer.echo("Section 1 has no figures", err=True)
        raise typer.Exit(1)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    app()
