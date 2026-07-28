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
Stage 07 function-path smoke (text-only): ensure reflow_section_with_llm returns JSON.

Iterative step:
- Load pre-step07 sections (04_sections.json preferred, else gold sample)
- Build minimal section dict (id/title/blocks/raw_text)
- Call reflow_section_with_llm(include_images=False, allow_fallback=False)
- Fail if JSON not returned
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
GOLD_04 = ROOT / "data/gold_standards/pipeline/004_section_builder_gs.json"


def _choose_section(payload: dict) -> dict:
    """Return the first section from a payload dictionary."""
    secs = (payload or {}).get("sections") or []
    if not secs:
        raise SystemExit("No sections available")
    return secs[0]


def _build_min_section(sec: dict) -> dict:
    """Build a minimal section dictionary from input section data."""
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
    """Load the stage 07 reflow section module."""
    import importlib.util

    p = Path("src/extractor/pipeline/steps/07_reflow_section.py").resolve()
    spec = importlib.util.spec_from_file_location("stage07", str(p))
    if not spec or not spec.loader:
        raise RuntimeError("Failed to load Stage 07 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


async def main_async() -> None:
    """Initialize and configure environment variables for async execution."""
    load_dotenv(find_dotenv(usecwd=True) or None)
    os.environ.setdefault("LITELLM_HTTPX", "1")
    os.environ.setdefault("LITELLM_DEBUG", "1")
    os.environ.setdefault("LITELLM_DROP_PARAMS", "0")
    # Simplify Stage07 expectations to text-only JSON for a minimal passing path
    os.environ.setdefault("STAGE07_SCHEMA_MODE", "text")
    os.environ.setdefault("STAGE07_COMPACT_PROMPT", "1")
    os.environ.setdefault("STAGE07_TRIM_CHARS", "2000")
    os.environ.setdefault("STAGE07_GEMINI_SHIM", "1")
    sys.path.insert(0, os.path.abspath("src"))

    stage07 = _load_stage07()
    reflow_section_with_llm = getattr(stage07, "reflow_section_with_llm")

    # Load pre-step07
    if RESULTS_04.exists():
        payload = json.loads(RESULTS_04.read_text(encoding="utf-8"))
    else:
        gold = json.loads(GOLD_04.read_text(encoding="utf-8"))
        payload = gold.get("sample") or {}
    sec = _choose_section(payload)
    section_min = _build_min_section(sec)

    results_dir = ROOT / "data/results/pipeline"
    out = await reflow_section_with_llm(
        section_min, results_dir, include_images=False, allow_fallback=False
    )
    # Require JSON presence
    ok = isinstance(out, dict) and (
        isinstance(out.get("reflowed_json"), dict) or isinstance(out.get("reflowed_text"), str)
    )
    if not ok:
        raise SystemExit("Stage07 function smoke (text-only) did not return JSON")

    art = Path("scripts/artifacts")
    art.mkdir(parents=True, exist_ok=True)
    (art / "stage07_stage_call_text.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("OK: Stage07 function (text-only) returned JSON")


app = typer.Typer(add_completion=False, help="Stage 07 function-path smoke (text-only)")


@app.command()
def main() -> None:
    """Run the main async application."""
    asyncio.run(main_async())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        app()
    else:
        asyncio.run(main_async())
