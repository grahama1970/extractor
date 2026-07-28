#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv",
#   "numpy",
#   "pandas",
#   "litellm>=1.74.7",
#   "tqdm",
#   "loguru",
#   "rich",
#   "pillow",
#   "httpx",
#   "json-repair",
#   "urlextract",
#   "strip-tags",
# ]
# ///
from __future__ import annotations

import os
import sys
import json
from pathlib import Path
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: Stage 07 complex CLI strict JSON")


def run_smoke(results: Path) -> None:
    """Run a smoke test, preparing environment and upstream artifacts."""
    load_dotenv(find_dotenv(usecwd=True) or None)
    os.environ.setdefault("LITELLM_HTTPX", "1")
    os.environ.setdefault("LITELLM_DEBUG", "1")

    # Ensure upstream artifacts via CLI
    import subprocess

    pdf_path = Path("data/input/pipeline/BHT_CV32A65X_marked.pdf")
    cmd_prep = [
        sys.executable,
        str(Path("src/extractor/pipeline/tools/quick_smoke.py")),
        "--pdf",
        str(pdf_path),
    ]
    env = os.environ.copy()
    env.setdefault("LITELLM_HTTPX", "1")
    env.setdefault("LITELLM_DEBUG", "1")
    env.setdefault("LITELLM_DROP_PARAMS", "0")
    env.setdefault("STAGE07_FORCE_MINIMAL_CALL", "1")
    env.setdefault("STAGE07_SCHEMA_MODE", "reflow_json")
    env.setdefault("STAGE07_MINIMAL_JSON", "1")
    proc_prep = subprocess.run(cmd_prep, env=env)
    if proc_prep.returncode != 0:
        raise SystemExit("quick_smoke failed to produce upstream artifacts")

    sec = results / "04_section_builder/json_output/04_sections.json"
    tab = results / "05_table_extractor/json_output/05_tables.json"
    fig = results / "06_figure_extractor/json_output/06_figures.json"
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
        "-o",
        str(results),
    ]
    proc = subprocess.run(cmd, env=env)
    if proc.returncode != 0:
        raise SystemExit("Stage 07 complex CLI failed")

    out_json = results / "07_reflow_section/json_output/07_reflowed.json"
    data = json.loads(out_json.read_text())
    ok = False
    if isinstance(data, dict) and isinstance(data.get("reflowed_sections"), list):
        for x in data["reflowed_sections"]:
            if isinstance(x, dict) and (
                isinstance(x.get("reflowed_json"), dict) or isinstance(x.get("reflowed_text"), str)
            ):
                ok = True
                break
    if not ok:
        raise SystemExit("Stage 07 complex strict JSON failed (no reflowed_json)")
    typer.echo("OK: Stage 07 complex strict JSON returned")


@app.command()
def main(results: Path = typer.Option(Path("data/results/pipeline"), "--results")):
    """Run smoke test using results path."""
    run_smoke(results)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        app()
    else:
        run_smoke(Path("data/results/pipeline"))
