#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""Smoke: Stage 07 JSON schema validation (minimal).

Find latest 07_reflowed.json under data/results and validate key shape.
SKIP if none found.
"""
from __future__ import annotations

import json
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)


def _find_latest(root: Path) -> Path | None:
    """Return the most recent JSON file path from a directory."""
    cands = sorted(
        root.rglob("07_reflow_section/json_output/07_reflowed.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return cands[0] if cands else None


@app.command()
def main(root: Path = typer.Option(Path("data/results"))):
    """Load and validate Stage 07 JSON from the latest file."""
    p = _find_latest(root)
    if not p or not p.exists():
        print("SKIP: no Stage 07 reflowed JSON found")
        raise typer.Exit(0)
    data = json.loads(p.read_text())
    ok = isinstance(data, dict) and isinstance(data.get("reflowed_sections"), list)
    if not ok:
        typer.echo("Invalid Stage 07 structure", err=True)
        raise typer.Exit(1)
    # Minimal per-section checks
    for s in data["reflowed_sections"][:3]:
        if not isinstance(s, dict):
            continue
        assert "id" in s and "title" in s
    print("OK: Stage 07 schema valid (minimal)")


if __name__ == "__main__":
    app()
