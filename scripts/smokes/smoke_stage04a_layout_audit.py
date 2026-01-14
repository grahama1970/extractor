#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
from __future__ import annotations

import json
import shutil
from pathlib import Path

import typer

from extractor.pipeline.steps.s04a_layout_audit import run as run_layout_audit

app = typer.Typer(
    add_completion=False,
    help="Smoke: Stage 04a layout audit validates canonical reading order.",
)


def _write_sections(path: Path) -> None:
    data = {
        "sections": [
            {
                "id": "s-intro",
                "title": "Intro",
                "blocks": [
                    {
                        "block_id": "b1",
                        "block_type": "text",
                        "page_index": 0,
                        "bbox": [50, 80, 500, 120],
                    },
                    {
                        "block_id": "b2",
                        "block_type": "text",
                        "page_index": 0,
                        "bbox": [50, 140, 500, 200],
                    },
                ],
            },
            {
                "id": "s-impl",
                "title": "Implementation Notes",
                "blocks": [
                    {
                        "block_id": "b3",
                        "block_type": "bullet",
                        "page_index": 1,
                        "bbox": [60, 90, 520, 130],
                    }
                ],
            },
        ]
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


@app.command()
def main(
    results: Path = typer.Option(
        Path("data/results/pipeline/smokes/layout_audit"),
        "--results",
        "-o",
        help="Scratch pipeline directory for generated artifacts.",
    )
) -> None:
    if results.exists():
        shutil.rmtree(results)
    sections_dir = results / "04_section_builder" / "json_output"
    sections_dir.mkdir(parents=True, exist_ok=True)
    sections_path = sections_dir / "04_sections.json"
    _write_sections(sections_path)

    try:
        run_layout_audit(results)
    except Exception as exc:  # pragma: no cover - smoke script
        typer.echo(f"Layout audit failed: {exc}", err=True)
        raise typer.Exit(code=1)

    audit_path = results / "04a_layout_audit" / "json_output" / "04a_layout_audit.json"
    if not audit_path.exists():
        typer.echo("Layout audit JSON missing", err=True)
        raise typer.Exit(code=2)
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    if not payload.get("ok"):
        typer.echo(f"Layout audit reported errors: {payload}", err=True)
        raise typer.Exit(code=3)
    typer.echo("OK: Stage 04a layout audit passed on synthetic hierarchy.")


if __name__ == "__main__":
    app()
