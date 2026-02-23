#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12.3",
#   "pillow>=10.1.0",
# ]
# ///
import base64
import json
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from extractor.pipeline.utils.litellm_call import require_scillm_env, normalize_model_alias
import litellm

app = typer.Typer(help="Minimal VLM chat.completions smoke with image_url content")


def _b64(p: Path) -> str:
    return base64.b64encode(p.read_bytes()).decode("utf-8")


@app.command()
def run(
    image_path: Path = typer.Argument(..., exists=True, readable=True),
    context: str = typer.Option("Figure description test", "--context"),
    model: Optional[str] = typer.Option(None, "--model", help="Overrides env VLM"),
):
    require_scillm_env()
    raw_model = (
        model or os.getenv("LITELLM_VLM_MODEL") or os.getenv("LITELLM_MED_VLM_MODEL") or ""
    ).strip()
    if not raw_model:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "No VLM model configured (set LITELLM_VLM_MODEL or LITELLM_MED_VLM_MODEL)",
                },
                indent=2,
            )
        )
        sys.exit(2)
    mdl = normalize_model_alias(raw_model)
    b64 = _b64(image_path)
    user_content = [
        {"type": "text", "text": context[:2000]},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    ]
    try:
        resp = litellm.completion(
            model=mdl,
            messages=[
                {
                    "role": "system",
                    "content": "You write concise technical figure descriptions (2–3 sentences).",
                },
                {"role": "user", "content": user_content},
            ],
            timeout=25,
            max_tokens=256,
            temperature=0.2,
            custom_llm_provider="openai",
        )
        # Normalize output
        content = None
        if isinstance(resp, dict):
            content = resp.get("choices", [{}])[0].get("message", {}).get("content")
        else:
            content = (
                getattr(getattr(resp, "choices", [None])[0], "message", {}).get("content")
                if hasattr(resp, "choices")
                else None
            )
        ok = bool((content or "").strip())
        print(json.dumps({"ok": ok, "model": mdl, "content": (content or "")[:400]}, indent=2))
        sys.exit(0 if ok else 3)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e), "model": mdl}, indent=2))
        sys.exit(4)


if __name__ == "__main__":
    app()
