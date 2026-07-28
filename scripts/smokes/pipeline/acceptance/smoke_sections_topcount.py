#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv>=1.0.0,<2",
# ]
# ///
"""
Acceptance: Top-level sections count and titles from Stage 07.
Writes a summary and titles list; optional strict mode via ACCEPT_STRICT=1.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)

PDF = Path("data/input/pipeline/BHT_CV32A65X_with_requirements.pdf")
OUT = Path("data/results/with_requirements_sections")


def ensure_stage07() -> Path:
    """Ensure stage 07 output exists, creating it if necessary."""
    OUT.mkdir(parents=True, exist_ok=True)
    p07 = OUT / "07_reflow_section/json_output/07_reflowed.json"
    if p07.exists():
        return p07
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
        raise SystemExit("extract failed")
    return p07


@app.command()
def main(expected: int = typer.Option(2)):
    """Extract titles from top-level sections in loaded JSON data."""
    p07 = ensure_stage07()
    d = json.loads(p07.read_text())
    secs = d.get("reflowed_sections", [])
    levels = [s.get("level") for s in secs if isinstance(s.get("level"), int)]
    minlvl = min(levels) if levels else None
    tops = [s for s in secs if s.get("level") == minlvl] if minlvl is not None else secs
    titles = [str(s.get("title") or "").strip() for s in tops]
    report = {"top_sections": len(tops), "titles": titles}
    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts") / "sections_topcount_summary.json").write_text(
        json.dumps(report, indent=2)
    )
    strict = os.getenv("ACCEPT_STRICT", "").lower() in {"1", "true", "yes", "y"}
    if strict and len(tops) != expected:
        typer.echo(f"Expected {expected} top sections, got {len(tops)}", err=True)
        raise typer.Exit(1)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    app()
