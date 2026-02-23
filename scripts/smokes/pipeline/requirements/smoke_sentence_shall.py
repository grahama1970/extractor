#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv>=1.0.0,<2",
# ]
# ///
"""
Smoke: Extract simple "shall" requirements from corpus text and prove via Lean4 CLI (offline).

This isolates pre-prover extraction for plain sentences containing modal verbs
and validates the Lean4 CLI integration with --deterministic/--no-llm.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import typer

app = typer.Typer(add_completion=False)


def extract_shall_sentences(text: str) -> list[str]:
    # Very small, deterministic heuristic for smoke only
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    out: list[str] = []
    for s in sents:
        if re.search(r"\b(shall|must|will|should)\b", s, flags=re.IGNORECASE):
            out.append(s.strip())
    return out


@app.command()
def main():
    lean_cli = Path("/home/graham/workspace/experiments/lean4/src/lean4_prover/cli_mini.py")
    if not lean_cli.exists():
        print("SKIP: Lean4 CLI not found; install lean4_prover first.")
        raise typer.Exit(0)

    text = (
        "The controller shall reset to zero on power-up. "
        "The logger must retain the last 100 entries. "
        "Background info only."
    )
    reqs = extract_shall_sentences(text)

    items = [
        {"requirement": r, "metadata": {"section_id": f"S-{i:03d}"}} for i, r in enumerate(reqs)
    ]

    tmp = Path("/tmp/lean_shall_in.json")
    tmp.write_text(json.dumps(items, indent=2))
    out = Path("/tmp/lean_shall_out.json")

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
    (Path("scripts/artifacts") / "req_sentence_shall_summary.json").write_text(
        json.dumps(summary, indent=2)
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    app()
