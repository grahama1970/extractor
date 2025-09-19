#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""Online (opt‑in): single rationale call via litellm_call.

SKIP if no provider keys. This mirrors Stage 11 rationale generation style.
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
    import sys
    src_dir = str((Path(__file__).resolve().parents[4] / "src").resolve())
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    from extractor.pipeline.utils.litellm_call import litellm_call

    async def run_one():
        a = "Alpha is the first letter of the Greek alphabet."
        b = "Alphabet derives from alpha and beta."
        prompt = f"Explain in one sentence why these are related. A: {a} B: {b}"
        params = {
            "model": os.getenv("LITELLM_MODEL", "openai/gpt-4o-mini"),
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 64,
        }
        res = await litellm_call([params], wrap_json=False, concurrency=1, desc="stage11-rationale-one", session_id="smokes-online")
        txt = (res[0].content if res else "")
        ok = bool(txt)
        Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
        (Path("scripts/artifacts")/"online_stage11_rationale.json").write_text(json.dumps({"ok": ok}, indent=2))
        if not ok:
            raise SystemExit(1)

    asyncio.run(run_one())
    print("OK: stage11-like rationale")


if __name__ == "__main__":
    app()

