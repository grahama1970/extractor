#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12.0",
# ]
# ///
"""
Quick scillm VLM sanity probe against a Chutes OpenAI‑compatible gateway.

- Proves header/auth shape (x-api-key, no Bearer) and image payload handling.
- Works with ANY image path; defaults to model from LITELLM_LARGE_VLLM_MODEL.

Usage
  source .venv/bin/activate && set -a && source .env && set +a
  python debug/scillm_vlm_probe.py --image src/extractor/pipeline/steps/image.png \
    --model "${LITELLM_LARGE_VLLM_MODEL:-Qwen/Qwen3-VL-235B-A22B-Instruct}" --timeout 30

Exits 0 on success; prints JSON snippets for two checks.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import sys
import typer

try:
    from scillm import completion as sc_completion
except Exception as e:  # pragma: no cover
    print(f"scillm import failed: {e}", file=sys.stderr)
    sys.exit(2)


app = typer.Typer(add_completion=False)


def _to_data_url(p: Path) -> str:
    b = p.read_bytes()
    b64 = base64.b64encode(b).decode("utf-8")
    # assume png if unknown; most gateways ignore mime
    return f"data:image/png;base64,{b64}"


@app.command()
def run(
    image: Path = typer.Option(..., exists=True, dir_okay=False, help="Path to any image file"),
    model: str = typer.Option(
        os.getenv("LITELLM_LARGE_VLLM_MODEL", "Qwen/Qwen3-VL-235B-A22B-Instruct"),
        help="VL model id",
    ),
    timeout: int = typer.Option(30, min=5, max=120),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    base = os.getenv("CHUTES_API_BASE", "").strip()
    key = os.getenv("CHUTES_API_KEY", "").strip()
    if not (base and key):
        print("CHUTES_API_BASE / CHUTES_API_KEY required in env", file=sys.stderr)
        raise typer.Exit(2)

    du = _to_data_url(image)

    def _call(messages, resp_format=None):
        return sc_completion(
            model=model,
            api_base=base,
            api_key=None,
            custom_llm_provider="openai_like",
            messages=messages,
            response_format=resp_format,
            temperature=0,
            timeout=timeout,
            api_key=key,
        )

    # Check 1: strict JSON echo with image present
    messages_ok = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": 'Return only {"ok":true} as JSON.'},
                {"type": "image_url", "image_url": {"url": du}},
            ],
        }
    ]
    r1 = _call(messages_ok, {"type": "json_object"})
    c1 = (r1.get("choices") or [{}])[0].get("message", {}).get("content", "")
    if verbose:
        print("JSON echo:", c1)
    try:
        j1 = json.loads(c1)
        assert j1 == {"ok": True}, f"unexpected JSON: {j1}"
    except Exception as e:  # pragma: no cover
        print(f"[FAIL] JSON echo check: {e}\nRaw: {c1[:200]}", file=sys.stderr)
        raise typer.Exit(1)

    # Check 2: description JSON (short)
    messages_desc = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": 'Describe the image in <=25 words. Return {"desc": string} as JSON.',
                },
                {"type": "image_url", "image_url": {"url": du}},
            ],
        }
    ]
    r2 = _call(messages_desc, {"type": "json_object"})
    c2 = (r2.get("choices") or [{}])[0].get("message", {}).get("content", "")
    if verbose:
        print("Desc JSON:", c2)
    try:
        j2 = json.loads(c2)
        assert (
            isinstance(j2, dict) and isinstance(j2.get("desc", ""), str) and j2.get("desc").strip()
        ), "missing desc"
    except Exception as e:  # pragma: no cover
        print(f"[FAIL] Desc JSON check: {e}\nRaw: {c2[:200]}", file=sys.stderr)
        raise typer.Exit(1)

    print(json.dumps({"ok": True, "desc": j2.get("desc", "")}, ensure_ascii=False))


if __name__ == "__main__":
    app()
