#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "litellm>=1.74.7",
#   "tqdm",
#   "loguru",
#   "pillow",
#   "httpx",
#   "json-repair",
# ]
# ///
# ///
# dependencies += ["typer>=0.12"]
# ///
"""
Simplest smoke: Get ANY JSON back from Gemini given:
- Pre-step07 sections JSON (real results preferred, else gold sample)
- One section image (if available)
- A prompt loaded from assets

Uses litellm_call with minimal params. Debug on. No schema, no generation_config,
no max_output_tokens. Fails if response is not parseable JSON.
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
PROMPT_TXT = ROOT / "scripts/smokes/pipeline/assets/prompt_any_json.txt"


def _choose_section(payload: dict) -> dict:
    secs = (payload or {}).get("sections") or []
    if not secs:
        raise SystemExit("No sections available")
    return secs[0]


def _context_from_section(sec: dict) -> str:
    title = sec.get("title") or "Untitled"
    blocks = sec.get("blocks") or []
    texts = [b.get("text") for b in blocks if isinstance(b, dict) and b.get("text")]
    joined = " ".join(t.strip() for t in texts if isinstance(t, str))[:1200]
    return f"Section: {title}\nText: {joined}"


def _find_section_image(sec: dict) -> Path | None:
    vp = sec.get("visual_path") or sec.get("image_path")
    if isinstance(vp, str):
        p = (ROOT / vp).resolve()
        if p.exists():
            return p
    # Common results location / naming
    candidates = [
        ROOT / "data/results/pipeline/04_section_builder/image_output/sec_0001.png",
    ]
    sid = sec.get("id")
    if isinstance(sid, str) and sid:
        candidates.append(ROOT / f"data/results/pipeline/04_section_builder/image_output/{sid}.png")
    for c in candidates:
        if c.exists():
            return c
    return None


async def main_async() -> None:
    load_dotenv(find_dotenv(usecwd=True) or None)
    os.environ.setdefault("LITELLM_HTTPX", "1")
    os.environ.setdefault("LITELLM_DEBUG", "1")
    os.environ.setdefault("LITELLM_DROP_PARAMS", "0")
    sys.path.insert(0, os.path.abspath("src"))

    from extractor.pipeline.utils.litellm_call import litellm_call

    if not PROMPT_TXT.exists():
        raise SystemExit(f"Prompt file not found: {PROMPT_TXT}")
    prompt_guard = PROMPT_TXT.read_text(encoding="utf-8").strip()

    # Load pre-step07 sections
    if RESULTS_04.exists():
        payload = json.loads(RESULTS_04.read_text(encoding="utf-8"))
    else:
        gold = json.loads(GOLD_04.read_text(encoding="utf-8"))
        payload = gold.get("sample") or {}

    sec = _choose_section(payload)
    context = _context_from_section(sec)
    img = _find_section_image(sec)

    # Build messages; litellm_call will compress local image path → data URL
    parts = [{"type": "text", "text": context}]
    if img and img.exists():
        parts.append({"type": "image_url", "image_url": {"url": str(img)}})

    messages = [
        {"role": "system", "content": prompt_guard},
        {"role": "user", "content": parts},
    ]

    req = {
        "model": "gemini/gemini-2.5-flash",
        "messages": messages,
        "temperature": 0,
        # Keep it minimal — optional: uncomment to coax JSON
        # "response_format": {"type": "json_object"},
        "cache": {"no-cache": True},
    }

    out = await litellm_call([req], desc="stage07_any_json", export="results")
    r0 = out[0]
    if r0.exception is not None or not r0.content:
        print("Error or empty content:", r0.exception)
        raise SystemExit(2)

    # Verify it is ANY valid JSON
    try:
        _ = json.loads(r0.content)
    except Exception:
        print("Non-JSON response:", r0.content[:2000])
        raise SystemExit(3)

    out_dir = Path("scripts/artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "stage07_any_json.json").write_text(r0.content, encoding="utf-8")
    print("OK: ANY JSON returned from Gemini via litellm_call")


app = typer.Typer(add_completion=False, help="Stage 07 any JSON smoke")


@app.command()
def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        app()
    else:
        asyncio.run(main_async())
