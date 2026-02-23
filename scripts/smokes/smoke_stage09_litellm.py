#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "typer>=0.12",
# ]
# ///
from __future__ import annotations

import os
import json
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(
    add_completion=False, help="Smoke: Stage 09 summarizer (SciLLM-only; litellm path deprecated)"
)


@app.command()
def main(
    timeout: int = typer.Option(30, "--timeout"),
    model: str | None = typer.Option(None, "--model", "-m"),
):
    # Deprecated; SciLLM-only policy. Keep as no-op to avoid breaking references.
    load_dotenv(find_dotenv(usecwd=True) or None)
    outdir = os.path.join("scripts", "artifacts")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "stage09_litellm.json"), "w", encoding="utf-8") as f:
        json.dump(
            {"skip": True, "reason": "SciLLM-only; litellm smoke deprecated"}, f, ensure_ascii=False
        )
    typer.echo("SKIP: Stage 09 litellm smoke deprecated (SciLLM-only)")


if __name__ == "__main__":
    app()
