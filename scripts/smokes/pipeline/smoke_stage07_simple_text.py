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
#   "urlextract",
#   "strip-tags",
#   "numpy",
#   "pandas",
#   "typer>=0.12",
# ]
# ///
"""
Minimal Gemini structured-output smoke for Stage 07
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv, find_dotenv
try:
    import litellm  # type: ignore
    from litellm import Router  # type: ignore
except Exception:  # pragma: no cover
    print("SKIP: litellm not installed; smoke_stage07_simple_text skipped.")
    raise SystemExit(0)

ASSETS = Path("scripts/smokes/pipeline/assets")
SECTION_JSON = ASSETS / "section_sample.json"
SECTION_IMAGE_DATAURL = ASSETS / "section_image.dataurl.txt"

app = typer.Typer(add_completion=False, help="Stage 07 simple structured-output smoke")


def run_smoke() -> None:
    load_dotenv(find_dotenv(usecwd=True) or None)
    os.environ.setdefault("LITELLM_HTTPX", "1")
    os.environ.setdefault("LITELLM_DEBUG", "1")
    sys.path.insert(0, os.path.abspath("src"))

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gemini_key:
        print("GEMINI_API_KEY/GOOGLE_API_KEY not set")
        sys.exit(1)

    sec = json.loads(SECTION_JSON.read_text(encoding="utf-8"))
    img_data_url = SECTION_IMAGE_DATAURL.read_text(encoding="utf-8").strip()

    context = (
        f"Section: {sec.get('title','Untitled')}\n"
        f"Text: {sec.get('raw_text','').strip()}\n"
    )
    messages = [
        {"role": "system", "content": "Return ONLY valid JSON. No prose, no fences."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": context},
                {"type": "image_url", "image_url": {"url": img_data_url}},
            ],
        },
    ]

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

    litellm.drop_params = False
    router = Router(
        model_list=[{
            "model_name": "gemini/gemini-2.5-flash",
            "litellm_params": {"model": "gemini/gemini-2.5-flash", "provider": "google", "api_key": gemini_key},
        }]
    )

    kwargs = {
        "response_format": {"type": "json_schema", "json_schema": {"schema": schema}},
        "temperature": 0,
    }

    try:
        resp = router.completion(model="gemini/gemini-2.5-flash", messages=messages, **kwargs)
    except Exception as e:
        em = str(e)
        if "Unable to process input image" in em:
            messages_no_img = [
                messages[0],
                {"role": "user", "content": [{"type": "text", "text": context}]},
            ]
            resp = router.completion(model="gemini/gemini-2.5-flash", messages=messages_no_img, **kwargs)
        else:
            raise

    content = None
    try:
        ch = resp.get("choices") or []
        if ch:
            msg = ch[0].get("message") or {}
            content = msg.get("content")
    except Exception:
        pass

    if not isinstance(content, str) or not content.strip():
        print("Empty content from Router")
        print(json.dumps({"raw": resp}, ensure_ascii=False)[:2000])
        sys.exit(2)

    out_dir = Path("scripts/artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "stage07_simple.json").write_text(content, encoding="utf-8")
    print("OK: Stage 07 simple (direct) strict JSON returned")


@app.command()
def main() -> None:
    run_smoke()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        app()
    else:
        run_smoke()
