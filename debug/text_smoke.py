#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12.3",
# ]
# ///
import json
import os
import sys
from typing import Optional
import typer
from extractor.pipeline.utils.litellm_call import require_scillm_env
import litellm

app = typer.Typer(help="Minimal OpenAI-compatible chat text smoke via CHUTES")


@app.command()
def run(model: Optional[str] = typer.Option(None, "--model", help="Override text model id")):
    require_scillm_env()
    mdl = (
        model or os.getenv("LITELLM_DEFAULT_MODEL") or os.getenv("LITELLM_SMALL_TEXT_MODEL") or ""
    ).strip()
    if not mdl:
        print(json.dumps({"ok": False, "error": "No text model configured"}, indent=2))
        sys.exit(2)
    try:
        resp = litellm.completion(
            model=mdl.split("openai/", 1)[-1],
            messages=[{"role": "user", "content": 'Return only {"ok":true} as JSON.'}],
            response_format={"type": "json_object"},
            max_tokens=20,
            custom_llm_provider="openai",
            timeout=15,
        )
        content = None
        if isinstance(resp, dict):
            content = resp.get("choices", [{}])[0].get("message", {}).get("content")
        else:
            content = (
                getattr(getattr(resp, "choices", [None])[0], "message", {}).get("content")
                if hasattr(resp, "choices")
                else None
            )
        ok = False
        try:
            obj = json.loads(content or "{}")
            ok = bool(obj.get("ok") is True)
        except Exception:
            ok = False
        print(json.dumps({"ok": ok, "model": mdl, "content": content}, indent=2))
        sys.exit(0 if ok else 3)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e), "model": mdl}, indent=2))
        sys.exit(4)


if __name__ == "__main__":
    app()
