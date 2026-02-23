#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""Smoke: Stage 10 flattened JSON schema validation (minimal).

Find latest 10_flattened_data.json under data/results and validate list shape
and presence of required keys.
SKIP if none found.
"""
from __future__ import annotations

import json
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)


def _find_latest(root: Path) -> Path | None:
    cands = sorted(
        root.rglob("10_arangodb_exporter/json_output/10_flattened_data.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return cands[0] if cands else None


@app.command()
def main(root: Path = typer.Option(Path("data/results"))):
    p = _find_latest(root)
    if not p or not p.exists():
        print("SKIP: no Stage 10 flattened JSON found")
        raise typer.Exit(0)
    data = json.loads(p.read_text())
    if not isinstance(data, list):
        typer.echo("Stage 10 must be a list", err=True)
        raise typer.Exit(1)
    required = {"_key", "doc_id", "section_id", "text_content"}
    for o in data[:5]:
        if not isinstance(o, dict) or not required.issubset(o.keys()):
            typer.echo("Invalid Stage 10 object (missing required keys)", err=True)
            raise typer.Exit(1)
    print("OK: Stage 10 schema valid (minimal)")


if __name__ == "__main__":
    app()
