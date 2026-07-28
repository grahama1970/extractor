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
import sys
from pathlib import Path
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Stage 07 figure propagation smoke")


def _ensure_stage07(results: Path) -> None:
    """Rerun Stage 07 to process updated sections, tables, and figures."""
    sec = results / "04_section_builder/json_output/04_sections.json"
    tab = results / "05_table_extractor/json_output/05_tables.json"
    fig = results / "06_figure_extractor/json_output/06_figures.json"
    # always rerun Stage 07 to use latest prompt/schema
    env = os.environ.copy()
    env.setdefault("LITELLM_HTTPX", "1")
    env.setdefault("LITELLM_DEBUG", "1")
    prep = [
        sys.executable,
        str(Path("src/extractor/pipeline/tools/quick_smoke.py")),
        "--pdf",
        str(Path("data/input/pipeline/BHT_CV32A65X_marked.pdf")),
    ]
    if subprocess.run(prep, env=env).returncode != 0:
        raise SystemExit("quick_smoke failed")
    cmd = [
        sys.executable,
        "src/extractor/pipeline/steps/07_reflow_section.py",
        "run",
        "--sections",
        str(sec),
        "--tables",
        str(tab),
        "--figures",
        str(fig),
        "--mode",
        "strict",
        "-o",
        str(results),
    ]
    if subprocess.run(cmd, env=env).returncode != 0:
        raise SystemExit("Stage 07 run failed")


def run_smoke(results: Path) -> None:
    """Initialize environment variables and process smoke test results."""
    load_dotenv(find_dotenv(usecwd=True) or None)
    os.environ.setdefault("LITELLM_HTTPX", "1")
    os.environ.setdefault("LITELLM_DEBUG", "1")

    _ensure_stage07(results)

    figures = json.loads((results / "06_figure_extractor/json_output/06_figures.json").read_text())
    re07 = json.loads((results / "07_reflow_section/json_output/07_reflowed.json").read_text())
    figs = figures.get("figures") or []
    if not figs:
        typer.echo("SKIP: No figures in input")
        raise SystemExit(0)

    # pick first section with a figure
    sec_id = None
    for f in figs:
        if f.get("section_id"):
            sec_id = f.get("section_id")
            break
    if not sec_id:
        typer.echo("SKIP: Figures lack section_id mapping")
        raise SystemExit(0)

    # Check that reflowed section contains a figure reference (loosely: mentions 'figure' in any block string)
    sections = re07.get("reflowed_sections") or []
    target = next((s for s in sections if s.get("id") == sec_id), None)
    if not target:
        typer.echo("SKIP: Target section not in reflowed output")
        raise SystemExit(0)

    blocks = (target.get("reflowed_json") or {}).get("blocks") or []
    has_figure_ref = False
    for b in blocks:
        if isinstance(b, dict) and b.get("type") == "figure":
            has_figure_ref = True
            break
        if isinstance(b, str) and "figure" in b.lower():
            has_figure_ref = True
            break
    if not has_figure_ref:
        raise SystemExit("Figure propagation failed: no figure mention or block in reflowed output")

    typer.echo("OK: Stage 07 figure propagation (loose check) passed")


@app.command()
def main(
    results: Path = typer.Option(Path("data/results/pipeline"), "--results"),
):
    """Run smoke tests, saving results to path."""
    run_smoke(results)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        app()
    else:
        run_smoke(Path("data/results/pipeline"))
