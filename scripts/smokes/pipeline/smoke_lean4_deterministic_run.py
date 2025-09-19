#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""Lean4 deterministic run smoke.

Runs a tiny Lean4 CLI proof in deterministic mode when:
 - A Lean4 CLI is available (via LEAN4_CLI_CMD or default path), and
 - LiteLLM has a default model configured (OpenAI/Ollama, etc.).

Otherwise, exits 0 with a skip message (so CI/dev flows remain green without
provers or keys). Writes a small JSON result to scripts/artifacts/.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)


def _lean4_cli_cmd() -> list[str] | None:
    env = os.environ
    if env.get("LEAN4_CLI_CMD"):
        return shlex.split(env["LEAN4_CLI_CMD"])  # e.g., "python /path/cli_mini.py"
    default = Path("/home/graham/workspace/experiments/lean4/src/lean4_prover/cli_mini.py")
    if default.exists():
        return [sys.executable, str(default)]
    return None


def _litellm_ready() -> bool:
    return bool(
        os.environ.get("LITELLM_DEFAULT_MODEL")
        or os.environ.get("DEFAULT_LITELLM_MODEL")
        or os.environ.get("LITELLM_MODEL")
        or os.environ.get("OLLAMA_DEFAULT_MODEL")
    )


@app.command()
def main():
    artifacts = Path("scripts/artifacts"); artifacts.mkdir(parents=True, exist_ok=True)
    result_path = artifacts / "lean4_deterministic_run.json"

    cli = _lean4_cli_cmd()
    if not cli:
        print("SKIP: Lean4 CLI not configured.")
        result_path.write_text(json.dumps({"ok": False, "skipped": True, "reason": "no_cli"}, indent=2))
        raise typer.Exit(0)

    if not _litellm_ready():
        print("SKIP: LiteLLM default model not configured.")
        result_path.write_text(json.dumps({"ok": False, "skipped": True, "reason": "no_model"}, indent=2))
        raise typer.Exit(0)

    theorem = os.environ.get("LEAN4_TEST_THEOREM", "The sum of two even numbers is even")
    cmd = [*cli, "run", theorem, "--deterministic"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = proc.stdout.decode("utf-8", errors="ignore")
    ok = proc.returncode == 0
    result_path.write_text(json.dumps({"ok": ok, "cmd": cmd, "stdout": out[:4000]}, indent=2))
    if not ok:
        print("FAIL: Lean4 deterministic run failed.")
        raise typer.Exit(1)
    print("OK: Lean4 deterministic run")


if __name__ == "__main__":
    app()

