#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""Online (opt‑in): LiteLLM sanity smoke.

Runs the built-in litellm_call sanity check via its Typer CLI.
SKIP when no provider keys are configured.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)


def _has_keys() -> bool:
    for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "AZURE_OPENAI_KEY"):
        if os.getenv(k):
            return True
    return False


@app.command()
def main(model: str = typer.Option(os.getenv("LITELLM_MODEL", "openai/gpt-4o-mini"))):
    if not _has_keys():
        print("SKIP: no provider keys configured")
        raise typer.Exit(0)
    env = dict(**os.environ)
    src_dir = str((Path(__file__).resolve().parents[4] / "src").resolve())
    env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH','')}"
    cmd = [
        sys.executable,
        "-m",
        "extractor.pipeline.utils.litellm_call",
        "sanity",
        "--wrap-json",
        "--model",
        model,
    ]
    if subprocess.run(cmd, env=env).returncode != 0:
        typer.echo("sanity failed", err=True)
        raise typer.Exit(1)
    print("OK: litellm sanity")


if __name__ == "__main__":
    app()

