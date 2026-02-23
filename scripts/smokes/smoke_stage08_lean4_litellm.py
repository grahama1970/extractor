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


app = typer.Typer(
    add_completion=False, help="Smoke: Stage 08 Lean4 identify (litellm path, no prover)"
)


@app.command()
def main(
    timeout: int = typer.Option(40, "--timeout"),
    model: str | None = typer.Option(None, "--model", "-m"),
):
    try:
        load_dotenv(find_dotenv(usecwd=True) or None)
        os.environ.setdefault("LITELLM_HTTPX", "1")
        sys.path.insert(0, os.path.abspath("src"))
        import importlib.util
        from pathlib import Path

        p = Path("src/extractor/pipeline/steps/08_lean4_theorem_prover.py").resolve()
        spec = importlib.util.spec_from_file_location("stage08", str(p))
        if not spec or not spec.loader:
            raise SystemExit("Failed to load stage 08 module")
        stage08 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stage08)  # type: ignore[attr-defined]

        identify = getattr(stage08, "identify_requirements_in_section")

        # Minimal section with a clear requirement
        section = {
            "id": "s-lean",
            "title": "BHT Requirements",
            "reflowed_text": "The system shall record the last 8 branch outcomes. The table must list states.",
            "tables": [],
        }
        sem = asyncio.Semaphore(1)

        async def run_once():
            reqs, cons = await identify(section, sem)
            return reqs, cons

        reqs, cons = asyncio.run(run_once())
        ok = isinstance(reqs, list) and isinstance(cons, list)
        outdir = os.path.join("scripts", "artifacts")
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "stage08_litellm.json"), "w", encoding="utf-8") as f:
            json.dump(
                {"ok": ok, "requirements": reqs, "constraints": cons},
                f,
                ensure_ascii=False,
                indent=2,
            )
        if not ok:
            raise SystemExit("Stage 08 identify returned invalid types")
        typer.echo("OK: Stage 08 litellm identify returned lists")
    except Exception as e:
        typer.echo(f"Smoke failed: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    app()
