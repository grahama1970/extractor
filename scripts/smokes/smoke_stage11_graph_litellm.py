#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "typer>=0.12",
#   "httpx",
# ]
# ///
from __future__ import annotations

import os
import sys
import json
import asyncio
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: Stage 11 graph rationales (SciLLM-only; litellm path deprecated)")


@app.command()
def main(
    timeout: int = typer.Option(30, "--timeout"),
):
    # Deprecated; SciLLM-only policy. Keep as no-op to avoid breaking references.
    load_dotenv(find_dotenv(usecwd=True) or None)
    outdir = os.path.join("scripts", "artifacts")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "stage11_litellm.json"), "w", encoding="utf-8") as f:
        json.dump({"skip": True, "reason": "SciLLM-only; litellm smoke deprecated"}, f, ensure_ascii=False)
    typer.echo("SKIP: Stage 11 litellm smoke deprecated (SciLLM-only)")


if __name__ == "__main__":
    app()
