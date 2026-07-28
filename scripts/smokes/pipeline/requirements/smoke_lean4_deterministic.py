#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""
Smoke: Lean4 CLI deterministic proof path (no LLM) compiles a known theorem.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import typer

app = typer.Typer(add_completion=False)


@app.command()
def main():
    """Check for the existence of the Lean4 CLI file and exit."""
    lean_cli = Path("/home/graham/workspace/experiments/lean4/src/lean4_prover/cli_mini.py")
    if not lean_cli.exists():
        print("SKIP: Lean4 CLI not found")
        raise typer.Exit(0)

    items = [
        {
            "requirement": "The sum of two even numbers is even.",
            "metadata": {"section_id": "DET-1"},
        },
        {"requirement": "For all real x, x^2 + 1 > 0.", "metadata": {"section_id": "DET-2"}},
    ]
    tmp = Path("/tmp/lean_det_in.json")
    tmp.write_text(json.dumps(items, indent=2))
    out = Path("/tmp/lean_det_out.json")

    cmd = [
        "/home/graham/workspace/experiments/extractor/.venv/bin/python",
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
    env["PYTHONPATH"] = "/home/graham/workspace/experiments/lean4/src:" + env.get("PYTHONPATH", "")
    rc = subprocess.run(cmd, env=env).returncode
    if rc != 0 or not out.exists():
        typer.echo("Lean4 batch failed", err=True)
        raise typer.Exit(1)

    data = json.loads(out.read_text())
    proved = sum(1 for r in data.get("proof_results", []) if r.get("status") == "proved")
    summary = {
        "input_count": len(items),
        "proved": proved,
        "out": str(out),
    }
    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts") / "lean4_deterministic_summary.json").write_text(
        json.dumps(summary, indent=2)
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    app()
