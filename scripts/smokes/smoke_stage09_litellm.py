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
import asyncio
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: Stage 09 summarizer via litellm_call (no adapter)")


@app.command()
def main(
    timeout: int = typer.Option(30, "--timeout"),
    model: str | None = typer.Option(None, "--model", "-m"),
):
    try:
        load_dotenv(find_dotenv(usecwd=True) or None)
        os.environ.setdefault("LITELLM_HTTPX", "1")
        sys.path.insert(0, os.path.abspath("src"))
        import importlib.util
        from pathlib import Path

        p = Path("src/extractor/pipeline/steps/09_section_summarizer.py").resolve()
        spec = importlib.util.spec_from_file_location("stage09", str(p))
        if not spec or not spec.loader:
            raise SystemExit("Failed to load stage 09 module")
        stage09 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stage09)  # type: ignore[attr-defined]

        summarize_section = getattr(stage09, "summarize_section")
        from extractor.pipeline.utils.litellm_call import DEFAULT_MODEL as L_DEFAULT

        dummy_section = {
            "id": "s0",
            "title": "Branch History Table",
            "level": 2,
            "reflowed_text": "This section explains the BHT (Branch History Table) component and its behavior.",
        }
        mdl = model or os.getenv("LITELLM_DEFAULT_MODEL") or os.getenv("DEFAULT_LITELLM_MODEL") or L_DEFAULT

        async def run_once():
            sem = asyncio.Semaphore(1)
            # stage code reads model from env internally; temporarily set
            os.environ.setdefault("LITELLM_MODEL", mdl)
            return await summarize_section(
                section=dummy_section,
                semaphore=sem,
                previous_summaries=[],
                window_size=0,
                strict_json=True,
                request_timeout=timeout,
            )

        res = asyncio.run(run_once())
        ok = isinstance(res, dict) and res.get("success") is True and isinstance(res.get("summary_data", {}).get("summary"), str)
        artifact = {"ok": ok, "result": res}
        outdir = os.path.join("scripts", "artifacts")
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "stage09_litellm.json"), "w", encoding="utf-8") as f:
            json.dump(artifact, f, ensure_ascii=False, indent=2)
        if not ok:
            raise SystemExit("Invalid summarizer result")
        typer.echo("OK: Stage 09 litellm summary returned")
    except Exception as e:
        typer.echo(f"Smoke failed: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    app()
