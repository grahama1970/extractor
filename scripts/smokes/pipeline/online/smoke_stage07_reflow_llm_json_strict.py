#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""Online (opt‑in): Stage 07‑like JSON strict call via litellm_call.

Makes one JSON‑strict call to the provider to mimic Stage 07 guardrails.
SKIP if no provider keys.
"""
from __future__ import annotations

import os
from pathlib import Path
import json
import asyncio
import typer

app = typer.Typer(add_completion=False)


def _has_keys() -> bool:
    for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "AZURE_OPENAI_KEY"):
        if os.getenv(k):
            return True
    return False


@app.command()
def main():
    if not _has_keys():
        print("SKIP: no provider keys configured")
        raise typer.Exit(0)
    # Import with repo src path
    import sys
    src_dir = str((Path(__file__).resolve().parents[4] / "src").resolve())
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    from extractor.pipeline.utils.litellm_call import litellm_call
    from extractor.pipeline.utils.json_mode import JSON_SYSTEM_GUARD

    async def run_one():
        params = {
            "model": os.getenv("LITELLM_MODEL", "openai/gpt-4o-mini"),
            "messages": [
                {"role": "system", "content": JSON_SYSTEM_GUARD},
                {"role": "user", "content": "Return a JSON object: {\\"ok\\": true, \\"section\\": \\"Intro\\"}"},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 64,
        }
        res = await litellm_call([params], wrap_json=True, concurrency=1, desc="stage07-json-strict", session_id="smokes-online")
        out = res[0].content if res else {}
        try:
            obj = out if isinstance(out, dict) else json.loads(out)
            ok = bool(obj.get("ok"))
        except Exception:
            ok = False
        Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
        (Path("scripts/artifacts")/"online_stage07_json_strict.json").write_text(json.dumps({"ok": ok}, indent=2))
        if not ok:
            raise SystemExit(1)

    asyncio.run(run_one())
    print("OK: stage07-like JSON strict call")


if __name__ == "__main__":
    app()

