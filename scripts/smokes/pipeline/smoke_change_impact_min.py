#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""Smoke: change-impact tool reports added/removed/modified sections.

Create two tiny Stage 10 lists and assert the report contains keys.
"""
from __future__ import annotations

import json
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)


@app.command()
def main():
    out_dir = Path("data/results/cli_smokes/change_impact").resolve()
    tmp = out_dir / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    old = tmp / "old.json"
    new = tmp / "new.json"
    old.write_text(
        json.dumps(
            [
                {"_key": "a", "text_content": "Alpha", "section_id": "S1"},
                {"_key": "b", "text_content": "Beta", "section_id": "S2"},
            ],
            indent=2,
        )
    )
    new.write_text(
        json.dumps(
            [
                {"_key": "a", "text_content": "Alpha updated", "section_id": "S1"},
                {"_key": "c", "text_content": "Gamma", "section_id": "S3"},
            ],
            indent=2,
        )
    )
    import sys

    src_dir = str((Path(__file__).resolve().parents[3] / "src").resolve())
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    from extractor.pipeline.tools.change_impact import change_impact

    out = Path("scripts/artifacts/change_impact.json")
    res = change_impact(old, new, out)
    ok = res.get("ok") and len(res.get("impact_sections", [])) >= 1
    if not ok:
        typer.echo("change-impact report invalid", err=True)
        raise typer.Exit(1)
    print("OK: change-impact report")


if __name__ == "__main__":
    app()
