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
Stage 07 gold-preloaded JSON smoke
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
except Exception:
    print("SKIP: litellm not installed; smoke_stage07_gold_preloaded skipped.")
    raise SystemExit(0)

ASSETS = Path("scripts/smokes/pipeline/assets")
MESSAGES_JSON = ASSETS / "stage07_gold_messages.json"

app = typer.Typer(add_completion=False, help="Stage 07 gold-preloaded smoke")


def run_smoke() -> None:
    load_dotenv(find_dotenv(usecwd=True) or None)
    os.environ.setdefault("LITELLM_HTTPX", "1")
    os.environ.setdefault("LITELLM_DEBUG", "1")
    sys.path.insert(0, os.path.abspath("src"))

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gemini_key:
        print("GEMINI_API_KEY/GOOGLE_API_KEY not set")
        sys.exit(1)

    payload = json.loads(MESSAGES_JSON.read_text(encoding="utf-8"))
    messages = payload["messages"]
    schema = payload["schema"]

    litellm.drop_params = False
    router = Router(
        model_list=[
            {
                "model_name": "gemini/gemini-2.5-flash",
                "litellm_params": {
                    "model": "gemini/gemini-2.5-flash",
                    "provider": "google",
                    "api_key": gemini_key,
                },
            }
        ]
    )

    kwargs = {
        "response_format": {"type": "json_schema", "json_schema": {"schema": schema}},
        "temperature": 0,
    }

    resp = router.completion(model="gemini/gemini-2.5-flash", messages=messages, **kwargs)
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
    (out_dir / "stage07_gold_preloaded.json").write_text(content, encoding="utf-8")
    print("OK: Stage 07 gold-preloaded strict JSON returned")


@app.command()
def main() -> None:
    run_smoke()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        app()
    else:
        run_smoke()
