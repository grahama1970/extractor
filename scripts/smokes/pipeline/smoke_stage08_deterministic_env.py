#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "loguru>=0.7.0,<0.8",
# ]
# ///
"""Smoke: Stage 08 wires Lean4 CLI with --deterministic in offline/CI.

This checks the environment builder used by pipeline-run-all so we don't
depend on the Lean4 installation to validate the flag threading.
"""
from __future__ import annotations

import json
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)


@app.command()
def main():
    import sys
    repo_src = (Path(__file__).resolve().parents[3] / "src").resolve()
    if str(repo_src) not in sys.path:
        sys.path.insert(0, str(repo_src))
    from extractor.pipeline.run_all import _ensure_env

    results_dir = Path("/tmp/lean4_env_test")
    results_dir.mkdir(parents=True, exist_ok=True)

    # Use the default local CLI path; the function only formats the command string
    lean_cli = "python /home/graham/workspace/experiments/lean4/src/lean4_prover/cli_mini.py"

    env = _ensure_env(
        {},
        results_dir,
        arango_db="pdf_knowledge_base_test",
        session_id="smoke-deterministic",
        lean4_cli=lean_cli,
        deterministic_lean4=True,
    )

    cmd = env.get("LEAN4_CLI_CMD", "")
    ok = ("--deterministic" in cmd)

    report = {"ok": ok, "LEAN4_CLI_CMD": cmd}
    artifacts_dir = Path("scripts/artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "lean4_deterministic_env.json").write_text(json.dumps(report, indent=2))

    if not ok:
        typer.echo("LEAN4_CLI_CMD missing --deterministic when expected", err=True)
        raise typer.Exit(1)

    print("OK: deterministic flag present in LEAN4_CLI_CMD")


if __name__ == "__main__":
    app()
