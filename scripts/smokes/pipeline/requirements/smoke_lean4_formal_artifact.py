#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""
Smoke: Confirm Lean4 produces and compiles real Lean code (not a stub).
- Runs the Lean4 CLI (live) in deterministic/no-LLM mode
- Asserts at least one proved item
- Writes the proved Lean code to scripts/artifacts/proved_*.lean
"""
from __future__ import annotations
import os
import sys

import json
import subprocess
from pathlib import Path

import typer

app = typer.Typer(add_completion=False)


@app.command()
def main():
    """Check for the existence of the Lean4 CLI file and exit if missing."""
    lean_cli = Path(os.environ.get("LEAN4_CLI", Path.home() / "workspace/experiments/lean4/src/lean4_prover/cli_mini.py"))
    if not lean_cli.exists():
        print("SKIP: Lean4 CLI not found")
        raise typer.Exit(0)

    items = [
        {
            "requirement": "The sum of two even numbers is even.",
            "metadata": {"section_id": "FORM-1"},
        },
        {"requirement": "For all real x, x^2 + 1 > 0.", "metadata": {"section_id": "FORM-2"}},
    ]
    tmp = Path("/tmp/lean_formal_in.json")
    tmp.write_text(json.dumps(items, indent=2))
    out = Path("/tmp/lean_formal_out.json")

    cmd = [
        sys.executable,
        str(lean_cli),
        "batch",
        "--input-file",
        str(tmp),
        "--output-file",
        str(out),
        "--deterministic",
        "--no-llm",
        "--max-workers",
        "1",
    ]
    env = __import__("os").environ.copy()
    env["PYTHONPATH"] = str(Path(os.environ.get("LEAN4_SRC", Path.home() / "workspace/experiments/lean4/src"))) + ":" + env.get("PYTHONPATH", "")
    rc = subprocess.run(cmd, env=env).returncode
    if rc != 0 or not out.exists():
        typer.echo("Lean4 batch failed", err=True)
        raise typer.Exit(1)

    data = json.loads(out.read_text())
    results = [r for r in data.get("proof_results", []) if isinstance(r, dict)]
    proved = [r for r in results if r.get("status") == "proved" and r.get("lean_code")]
    artifacts = Path("scripts/artifacts")
    artifacts.mkdir(parents=True, exist_ok=True)

    saved = []
    for idx, r in enumerate(proved):
        code = str(r.get("lean_code", ""))
        if not code.strip():
            continue
        p = artifacts / f"proved_{idx:02d}.lean"
        p.write_text(code)
        saved.append(str(p))

    report = {
        "proved_count": len(proved),
        "saved": saved,
        "out_json": str(out),
    }
    (artifacts / "lean4_formal_artifact_summary.json").write_text(json.dumps(report, indent=2))
    if not proved:
        typer.echo("No proved items; cannot confirm formal artifact.", err=True)
        raise typer.Exit(1)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    app()
