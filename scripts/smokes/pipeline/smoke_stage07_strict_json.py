#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "typer>=0.12",
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
"""
Stage 07 structured output smoke (strict JSON, no fallback).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv, find_dotenv

ROOT = Path.cwd()
RESULTS_04 = ROOT / "data/results/pipeline/04_section_builder/json_output/04_sections.json"
RESULTS_05 = ROOT / "data/results/pipeline/05_table_extractor/json_output/05_tables.json"
RESULTS_06 = ROOT / "data/results/pipeline/06_figure_extractor/json_output/06_figures.json"

app = typer.Typer(add_completion=False, help="Stage 07 structured smoke")


def _load_stage07():
    """Load the Stage 07 module from a specified file path."""
    import importlib.util

    module_path = Path("src/extractor/pipeline/steps/07_reflow_section.py").resolve()
    spec = importlib.util.spec_from_file_location("stage07", str(module_path))
    if not spec or not spec.loader:
        raise RuntimeError("Failed to load Stage 07 module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def _ensure_dependencies() -> None:
    """Ensure required dependency files exist, running extraction if missing."""
    if not (RESULTS_04.exists() and RESULTS_05.exists() and RESULTS_06.exists()):
        from extractor.pipeline.tools.quick_smoke import run as quick_run  # type: ignore

        quick_run.callback(pdf=Path("data/input/pipeline/BHT_CV32A65X_marked.pdf"))  # type: ignore
        if not (RESULTS_04.exists() and RESULTS_05.exists() and RESULTS_06.exists()):
            raise SystemExit("Stage 01–06 artifacts missing even after quick_smoke")


def _choose_section(payload: dict) -> dict:
    """Return the first section from the payload or raise an error if none exist."""
    sections = (payload or {}).get("sections") or []
    if not sections:
        raise SystemExit("No sections available for Stage 07 smoke")
    return sections[0]


def _context_from_section(sec: dict) -> str:
    """Return formatted section title and concatenated text content."""
    title = sec.get("title") or "Untitled"
    blocks = sec.get("blocks") or []
    texts = [blk.get("text") for blk in blocks if isinstance(blk, dict) and blk.get("text")]
    joined = " ".join(t.strip() for t in texts if isinstance(t, str))[:1500]
    return f"Section: {title}\nText: {joined}"


async def run_smoke(results: Path) -> None:
    """Configure environment and run smoke tests."""
    load_dotenv(find_dotenv(usecwd=True) or None)
    os.environ.setdefault("LITELLM_HTTPX", "1")
    os.environ.setdefault("LITELLM_DEBUG", "1")
    os.environ.setdefault("LITELLM_DROP_PARAMS", "0")
    os.environ.setdefault("STAGE07_SCHEMA_MODE", "reflow_json")
    sys.path.insert(0, os.path.abspath("src"))

    _ensure_dependencies()

    stage07 = _load_stage07()
    consolidate_data = getattr(stage07, "consolidate_data")
    reflow_section_with_llm = getattr(stage07, "reflow_section_with_llm")

    sections = consolidate_data(RESULTS_04, RESULTS_05, RESULTS_06, None)
    if not sections:
        raise SystemExit("consolidate_data returned no sections")

    out = await reflow_section_with_llm(
        sections[0],
        results,
        include_images=True,
        allow_fallback=False,
        llm_timeout=60,
    )

    ok = isinstance(out, dict) and isinstance(out.get("reflowed_json"), dict)
    out_path = Path("scripts/artifacts") / "stage07_strict.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    if not ok:
        raise SystemExit("Stage 07 strict smoke failed (reflowed_json missing)")

    print("OK: Stage 07 strict JSON returned reflowed_json")


@app.command()
def main(results: Path = typer.Option(Path("data/results/pipeline"), "--results")) -> None:
    """Run the smoke test using results from the specified path."""
    asyncio.run(run_smoke(results))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        app()
    else:
        asyncio.run(run_smoke(Path("data/results/pipeline")))
