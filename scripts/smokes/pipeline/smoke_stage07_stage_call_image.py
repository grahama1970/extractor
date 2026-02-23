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
"""
Stage 07 function-path smoke (with image): ensure reflow_section_with_llm returns JSON.

Steps:
- Ensure upstream artifacts via quick_smoke (produces 01→06 and section images)
- Load pre-step07 sections (04_sections.json)
- Build minimal section dict (id/title/blocks/raw_text)
- Call reflow_section_with_llm(include_images=True, allow_fallback=False)
- Fail if JSON not returned
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv, find_dotenv

ROOT = Path.cwd()
RESULTS_04 = ROOT / "data/results/pipeline/04_section_builder/json_output/04_sections.json"
PDF_PATH = ROOT / "data/input/pipeline/BHT_CV32A65X_marked.pdf"


def _choose_section(payload: dict) -> dict:
    secs = (payload or {}).get("sections") or []
    if not secs:
        raise SystemExit("No sections available")
    return secs[0]


def _build_min_section(sec: dict) -> dict:
    title = sec.get("title") or "Untitled"
    blocks = sec.get("blocks") or []
    texts = [b.get("text") for b in blocks if isinstance(b, dict) and b.get("text")]
    raw = "\n".join(t.strip() for t in texts if isinstance(t, str))
    return {
        "id": sec.get("id") or "sec_smoke",
        "title": title,
        "level": sec.get("level", 1),
        "raw_text": raw,
        "blocks": [{"text": raw[:1200]}],
    }


def _load_stage07():
    import importlib.util

    p = Path("src/extractor/pipeline/steps/07_reflow_section.py").resolve()
    spec = importlib.util.spec_from_file_location("stage07", str(p))
    if not spec or not spec.loader:
        raise RuntimeError("Failed to load Stage 07 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


async def main_async() -> None:
    load_dotenv(find_dotenv(usecwd=True) or None)
    os.environ.setdefault("LITELLM_HTTPX", "1")
    os.environ.setdefault("LITELLM_DEBUG", "1")
    os.environ.setdefault("LITELLM_DROP_PARAMS", "0")
    # Minimal JSON + forced path for stability while iterating
    os.environ.setdefault("STAGE07_SCHEMA_MODE", "text")
    os.environ.setdefault("STAGE07_MINIMAL_JSON", "1")
    os.environ.setdefault("STAGE07_FORCE_MINIMAL_CALL", "1")
    sys.path.insert(0, os.path.abspath("src"))

    # Ensure upstream artifacts (section images)
    env = os.environ.copy()
    cmd = [sys.executable, "-m", "extractor.pipeline.tools.quick_smoke", "--pdf", str(PDF_PATH)]
    proc = subprocess.run(cmd, env=env)
    if proc.returncode != 0:
        raise SystemExit("quick_smoke failed to produce upstream artifacts")

    stage07 = _load_stage07()
    reflow_section_with_llm = getattr(stage07, "reflow_section_with_llm")

    payload = json.loads(RESULTS_04.read_text(encoding="utf-8"))
    sec = _choose_section(payload)
    section_min = _build_min_section(sec)

    results_dir = ROOT / "data/results/pipeline"
    out = await reflow_section_with_llm(
        section_min, results_dir, include_images=True, allow_fallback=False
    )
    ok = isinstance(out, dict) and (
        isinstance(out.get("reflowed_json"), dict) or isinstance(out.get("reflowed_text"), str)
    )
    if not ok:
        raise SystemExit("Stage07 function smoke (with image) did not return JSON")

    art = Path("scripts/artifacts")
    art.mkdir(parents=True, exist_ok=True)
    (art / "stage07_stage_call_image.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("OK: Stage07 function (with image) returned JSON")


app = typer.Typer(add_completion=False, help="Stage 07 function-path smoke (with image)")


@app.command()
def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        app()
    else:
        asyncio.run(main_async())
