#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv",
#   "litellm>=1.74.7",
#   "tqdm",
#   "loguru",
#   "pillow",
#   "httpx",
#   "json-repair",
#   "urlextract",
#   "strip-tags",
#   "numpy",
#   "pandas",
# ]
# ///
from __future__ import annotations

import os
import sys
import json
import asyncio
from pathlib import Path
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: Stage 07 medium (one image) strict JSON")


def _load_stage07():
    import importlib.util
    p = Path("src/extractor/pipeline/steps/07_reflow_section.py").resolve()
    spec = importlib.util.spec_from_file_location("stage07", str(p))
    if not spec or not spec.loader:
        raise RuntimeError("Failed to load Stage 07 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def run_smoke(results: Path) -> None:
    load_dotenv(find_dotenv(usecwd=True) or None)
    os.environ.setdefault("LITELLM_HTTPX", "1")
    os.environ.setdefault("LITELLM_DEBUG", "1")
    sys.path.insert(0, os.path.abspath("src"))
    # Ensure upstream artifacts via CLI
    import subprocess
    pdf_path = Path("data/input/pipeline/BHT_CV32A65X_marked.pdf")
    cmd = [
        sys.executable,
        str(Path("src/extractor/pipeline/tools/quick_smoke.py")),
        "run",
        "--pdf",
        str(pdf_path),
    ]
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        raise SystemExit("quick_smoke failed to produce upstream artifacts")

    stage07 = _load_stage07()
    consolidate_data = getattr(stage07, "consolidate_data")
    reflow_section_with_llm = getattr(stage07, "reflow_section_with_llm")

    sec_path = results / "04_section_builder/json_output/04_sections.json"
    tab_path = results / "05_table_extractor/json_output/05_tables.json"
    fig_path = results / "06_figure_extractor/json_output/06_figures.json"
    sections = consolidate_data(sec_path, tab_path, fig_path, None)
    if not sections:
        raise SystemExit("No sections to reflow")

    async def run_once():
        return await reflow_section_with_llm(sections[0], results, include_images=True, allow_fallback=False)

    out = asyncio.run(run_once())
    ok = isinstance(out, dict) and isinstance(out.get("reflowed_json"), dict)
    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    Path("scripts/artifacts/stage07_medium.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    if not ok:
        raise SystemExit("Stage 07 medium strict JSON failed")
    typer.echo("OK: Stage 07 medium strict JSON returned")


@app.command()
def main(results: Path = typer.Option(Path("data/results/pipeline"), "--results")):
    run_smoke(results)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        app()
    else:
        run_smoke(Path("data/results/pipeline"))
