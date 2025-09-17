#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "typer>=0.12",
#   "litellm>=1.74.7",
# ]
# ///
from __future__ import annotations

import os
import sys
import json
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: Stage 03 header verify via litellm_call (no adapter)")

TINY_PNG_DATA = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


@app.command()
def main(
    timeout: int = typer.Option(30, "--timeout"),
    model: str | None = typer.Option(None, "--model", "-m"),
):
    load_dotenv(find_dotenv(usecwd=True) or None)
    os.environ.setdefault("LITELLM_HTTPX", "1")
    sys.path.insert(0, os.path.abspath("src"))
    # Import stage module via importlib to avoid invalid identifier
    import importlib.util
    from pathlib import Path

    p = Path("src/extractor/pipeline/steps/03_suspicious_headers.py").resolve()
    spec = importlib.util.spec_from_file_location("stage03", str(p))
    if not spec or not spec.loader:
        raise SystemExit("Failed to load stage 03 module")
    stage03 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stage03)  # type: ignore[attr-defined]

    verify = getattr(stage03, "verify_header_with_llm")
    # minimal context and a 1x1 PNG; focus on call path working
    context = "Candidate header: 'BHT (Branch History Table) submodule' with numbering and spacing"
    image_b64 = TINY_PNG_DATA
    mdl = model or os.getenv("LITELLM_DEFAULT_MODEL") or os.getenv("DEFAULT_LITELLM_MODEL") or "gemini/gemini-2.5-flash"

    import asyncio

    async def run_once():
        return await verify(image_b64=image_b64, context_text=context, model=mdl)

    try:
        res = asyncio.run(run_once())
        ok = isinstance(res, dict) and "is_header" in res and isinstance(res.get("reasoning", ""), str)
        artifact = {
            "ok": ok,
            "model": mdl,
            "result": res,
        }
        outdir = os.path.join("scripts", "artifacts")
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "stage03_litellm.json"), "w", encoding="utf-8") as f:
            json.dump(artifact, f, ensure_ascii=False, indent=2)
        if not ok:
            raise SystemExit("Invalid verify_header payload")
        typer.echo("OK: Stage 03 litellm header verdict returned")
    except Exception as e:
        typer.echo(f"Smoke failed: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    app()
