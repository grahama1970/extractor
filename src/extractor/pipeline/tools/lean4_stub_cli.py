#!/usr/bin/env python3
"""
Lean4 Stub CLI (offline, deterministic)

Implements a minimal CLI compatible with Extractor's Stage 08 expectations.
- Supports:
  - run "<requirement>" [--deterministic] [--no-llm]
  - batch --input-file {input_json} --output-file {output_json} [--deterministic] [--no-llm]

Behavior:
- Never performs network calls.
- Returns a single-proof JSON with success=False by default ("unproved" path).
  This is sufficient for Extractor to proceed without crashing in offline CI.
"""
from __future__ import annotations

import json
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)


def _single_proof(requirement: str, deterministic: bool, no_llm: bool) -> dict:
    return {
        "success": False,
        "lean_code": "",
        "stdout": "",
        "stderr": "deterministic-no-llm-stub" if no_llm or deterministic else "stub",
        "return_code": 0,
        "error_messages": ["stub: no proving performed"],
        "proof_output": None,
    }


@app.command()
def run(
    requirement: str = typer.Argument(...),
    deterministic: bool = typer.Option(False, "--deterministic"),
    no_llm: bool = typer.Option(False, "--no-llm"),
):
    res = _single_proof(requirement, deterministic, no_llm)
    print(json.dumps(res, indent=2))


@app.command()
def batch(
    input_file: Path = typer.Option(..., "--input-file", exists=True, file_okay=True, readable=True),
    output_file: Path = typer.Option(..., "--output-file"),
    deterministic: bool = typer.Option(False, "--deterministic"),
    no_llm: bool = typer.Option(False, "--no-llm"),
):
    try:
        data = json.loads(input_file.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    # Accept both single-item payloads and simple dicts
    requirement = (
        data.get("requirement")
        if isinstance(data, dict)
        else ""
    )
    res = _single_proof(requirement or "", deterministic, no_llm)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(res, indent=2))


if __name__ == "__main__":
    app()

