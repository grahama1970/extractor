#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "tqdm",
#   "loguru",
#   "httpx",
#   "pillow",
#   "json-repair",
#   "typer>=0.12",
# ]
# ///
"""
Stage 07 strict JSON smoke using pre-07 gold input, via SciLLM Chutes helper.

What it does
- Loads pre-Step07 sections JSON (prefers real results, falls back to gold sample)
- Builds compact user text and attaches a section image by local path
- Calls SciLLM helper with a single request, using response_format=json_schema (strict), temperature=0

Outputs
- scripts/artifacts/stage07_gold_preloaded_scillm.json
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
GOLD_04 = ROOT / "data/gold_standards/pipeline/004_section_builder_gs.json"
RESULTS_04 = ROOT / "data/results/pipeline/04_section_builder/json_output/04_sections.json"


def _choose_section(sample: dict) -> dict:
    """Return the first section from a sample dictionary."""
    secs = (sample or {}).get("sections") or []
    if not secs:
        raise SystemExit("Gold sample has no sections")
    return secs[0]


def _context_from_section(sec: dict) -> str:
    """Return formatted section title and concatenated block texts."""
    title = sec.get("title") or "Untitled"
    blocks = sec.get("blocks") or []
    texts = [b.get("text") for b in blocks if isinstance(b, dict) and b.get("text")]
    joined = " ".join(t.strip() for t in texts if isinstance(t, str))
    return f"Section: {title}\nText: {joined[:1500]}"


def _find_section_image(sec: dict) -> Path | None:
    """Return the image path for a section, checking data and candidates."""
    vp = sec.get("visual_path") or sec.get("image_path")
    if isinstance(vp, str):
        p = (ROOT / vp).resolve()
        if p.exists():
            return p
    # Common results location
    candidates = [
        ROOT / "data/results/pipeline/04_section_builder/visual_output/sec_0001.png",
    ]
    sid = sec.get("id")
    if isinstance(sid, str) and sid:
        candidates.append(
            ROOT / f"data/results/pipeline/04_section_builder/visual_output/{sid}.png"
        )
    for cand in candidates:
        if cand.exists():
            return cand
    return None


app = typer.Typer(add_completion=False, help="Stage 07 gold-preloaded litellm smoke")


async def main_async() -> None:
    # Environment and module path
    load_dotenv(find_dotenv(usecwd=True) or None)
    sys.path.insert(0, os.path.abspath("src"))
    from scillm import completion

    if not (os.getenv("SCILLM_API_BASE", "http://localhost:4010") and os.getenv("SCILLM_PROXY_KEY", "sk-dev-proxy-123")):
        print("SCILLM_API_BASE/SCILLM_PROXY_KEY not set")
        raise SystemExit(1)

    # Prefer real 04 results; fallback to gold sample
    sample = {}
    if RESULTS_04.exists():
        try:
            real = json.loads(RESULTS_04.read_text(encoding="utf-8"))
            sample = {"sections": real.get("sections") or real.get("reflowed_sections") or []}
        except Exception:
            sample = {}
    if not sample:
        gold = json.loads(GOLD_04.read_text(encoding="utf-8"))
        sample = gold.get("sample") or {}

    sec = _choose_section(sample)
    context = _context_from_section(sec)
    img_path = _find_section_image(sec)

    # Build OpenAI-style messages, using a local image path
    parts: list[dict] = [{"type": "text", "text": context}]
    if img_path and img_path.exists():
        parts.append({"type": "image_url", "image_url": {"url": str(img_path)}})

    prompt_guard = (
        "Return ONLY valid JSON with keys: reflowed_json (object), ocr_corrections (object), "
        "improvements_made (string), summary (string)."
    )
    messages = [
        {"role": "system", "content": prompt_guard},
        {"role": "user", "content": parts},
    ]

    # Strict JSON schema
    schema = {
        "type": "object",
        "properties": {
            "reflowed_json": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "blocks": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title"],
                "additionalProperties": True,
            },
            "ocr_corrections": {
                "type": "object",
                "properties": {"_": {"type": "string"}},
                "additionalProperties": True,
            },
            "improvements_made": {"type": "string"},
            "summary": {"type": "string"},
        },
        "required": ["reflowed_json"],
        "additionalProperties": False,
    }

    model = os.getenv("CHUTES_TEXT_MODEL", "")
    res = completion(
        model=model,
        custom_llm_provider="openai_like",
        api_base=os.getenv("SCILLM_API_BASE", "http://localhost:4010"),
        api_key=os.getenv("SCILLM_PROXY_KEY", "sk-dev-proxy-123"),
        messages=messages,
        response_format={"type": "json_schema", "json_schema": {"schema": schema}},
        temperature=0,
        timeout=60,
    )
    content = res.get("choices", [{}])[0].get("message", {}).get("content")
    if not content:
        print("SciLLM helper returned empty content")
        raise SystemExit(2)

    out_dir = Path("scripts/artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "stage07_gold_preloaded_scillm.json").write_text(
        content if isinstance(content, str) else json.dumps(content), encoding="utf-8"
    )
    print("OK: Stage 07 gold-preloaded strict JSON via SciLLM helper returned")


@app.command()
def main() -> None:
    """Run the asynchronous main function in an event loop."""
    asyncio.run(main_async())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        app()
    else:
        asyncio.run(main_async())
