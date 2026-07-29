#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv",
#   "loguru",
#   "json-repair",
#   "httpx>=0.27",
#   "pillow",
#   "urlextract",
#   "strip-tags",
#   "litellm",
#   "tenacity>=8.2",
#   "redis",
# ]
# ///
"""Offline smoke for Stage 08: invoke Lean4 batch CLI directly (no PDF).

Checks that the Lean4 CLI produces a valid OUT.json object with proof_results and
section mapping. Uses --deterministic --no-llm to avoid network dependence.
"""
from __future__ import annotations
import sys

import json
import os
import subprocess
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)


@app.command()
def main(
    lean4_cli: str = typer.Option(
        os.environ.get("LEAN4_CLI_CMD", f"{sys.executable} {Path(os.environ.get('LEAN4_CLI', Path.home() / 'workspace/experiments/lean4/src/lean4_prover/cli_mini.py'))}"),
        help="Lean4 batch CLI entry (module or script path)",
    ),
    tmpdir: Path = typer.Option(Path("/tmp/lean4_smoke_stage08")),
):
    """Run Lean4 CLI process with temporary directory."""
    tmpdir.mkdir(parents=True, exist_ok=True)
    input_json = tmpdir / "in.json"
    output_json = tmpdir / "out.json"

    items = [
        {
            "requirement_text": "For all even m,n, m+n is even.",
            "context": {"section_id": "S1", "doc_id": "D123"},
        },
        {
            "requirement_text": "There are infinitely many primes.",
            "context": {"section_id": "S2", "doc_id": "D123"},
        },
    ]
    input_json.write_text(json.dumps(items, ensure_ascii=False))

    # Allow environment override through LEAN4_CLI_CMD template
    cli_template = os.getenv("LEAN4_CLI_CMD")
    if cli_template:
        cmd = cli_template.format(input_json=str(input_json), output_json=str(output_json))
    else:
        cmd = f"{lean4_cli} batch --input-file {input_json} --output-file {output_json} --deterministic --no-llm"

    env = os.environ.copy()
    # Ensure lean4_prover is importable when calling the module path directly
    env.setdefault("PYTHONPATH", str(Path(os.environ.get("LEAN4_SRC", Path.home() / "workspace/experiments/lean4/src"))))
    rc = subprocess.run(cmd, shell=True, env=env).returncode
    if rc != 0:
        typer.secho(f"Lean4 CLI failed: rc={rc}", fg=typer.colors.RED)
        raise typer.Exit(1)

    if not output_json.exists():
        typer.secho("OUT.json missing", fg=typer.colors.RED)
        raise typer.Exit(1)

    payload = json.loads(output_json.read_text())
    if not isinstance(payload, dict):
        typer.secho("OUT.json is not an object", fg=typer.colors.RED)
        raise typer.Exit(1)

    pr = payload.get("proof_results")
    if not isinstance(pr, list) or not pr:
        typer.secho("proof_results missing or empty", fg=typer.colors.RED)
        raise typer.Exit(1)

    for e in pr:
        item = e.get("item", {})
        src = item.get("source_details", {})
        if not src.get("section_id"):
            typer.secho("Missing item.source_details.section_id", fg=typer.colors.RED)
            raise typer.Exit(1)

    typer.secho("OK: Lean4 batch offline smoke passed", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
