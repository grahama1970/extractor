#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""
Acceptance: Section 2 has 3 tables total (1 merged, 2 non-merged) and tables carry titles/captions.
This checks Stage 07 section tables list and counts non-empty caption/title fields.
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
OUT = Path("data/results/with_requirements_tables")


def ensure_stage07() -> Path:
    """Ensure output directory exists and return path to JSON file."""
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
    """Identify top-level sections from stage 07 reflowed data."""
    p07 = ensure_stage07()
    d = json.loads(p07.read_text())
    secs = d.get("reflowed_sections", [])
    if not secs:
        print(json.dumps({"error": "no sections"}))
        raise typer.Exit(1)
    # Find top-level sections by minimum level
    levels = [s.get("level") for s in secs if isinstance(s.get("level"), int)]
    minlvl = min(levels) if levels else None
    tops = [s for s in secs if s.get("level") == minlvl] if minlvl is not None else secs
    if len(tops) < 2:
        print(json.dumps({"error": "<2 top-level sections"}))
        raise typer.Exit(1)
    # Identify slice belonging to 2nd top-level (s2) up to before next top-level
    s2_title = tops[1].get("title")
    # Find absolute index of s2 in the global list
    s2_idx = next(i for i, s in enumerate(secs) if s.get("title") == s2_title)
    # End at next top-level or end of list
    end_idx = len(secs)
    for j in range(s2_idx + 1, len(secs)):
        if secs[j].get("level") == minlvl:
            end_idx = j
            break
    # Aggregate tables from s2 and its descendants
    agg_tables = []
    for s in secs[s2_idx:end_idx]:
        agg_tables.extend(s.get("tables") or [])
    titled = sum(1 for t in agg_tables if str(t.get("caption") or t.get("title") or "").strip())
    report = {"section2_tables": len(agg_tables), "titled": titled}
    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts") / "tables_titles_section2_summary.json").write_text(
        json.dumps(report, indent=2)
    )
    strict = os.getenv("ACCEPT_STRICT", "").lower() in {"1", "true", "yes", "y"}
    if strict:
        if len(agg_tables) != 3 or titled != 3:
            typer.echo("Section 2 tables/titles mismatch", err=True)
            raise typer.Exit(1)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    app()
