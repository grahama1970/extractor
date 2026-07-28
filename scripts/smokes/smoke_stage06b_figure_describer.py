#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path

import typer

from extractor.pipeline.steps.s06b_figure_describer import run as run_figure_describer

app = typer.Typer(
    add_completion=False,
    help="Smoke: Stage 06b figure describer honors --skip-descriptions and preserves JSON.",
)

_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAF0lEQVR42mNgYGBgYGRkZGAAAwAA"
    "AP//AwA4fQn2X9PX/wAAAABJRU5ErkJggg=="
)


def _setup_fixture(root: Path) -> Path:
    """Create and configure directories and files for fixture setup."""
    figures_dir = root / "06_figure_extractor"
    json_dir = figures_dir / "json_output"
    json_dir.mkdir(parents=True, exist_ok=True)
    image_dir = figures_dir / "visual_output"
    image_dir.mkdir(parents=True, exist_ok=True)
    image_rel = "06_figure_extractor/visual_output/fig_001.png"
    (root / image_rel).write_bytes(_PNG_BYTES)
    figures_payload = {
        "figures": [
            {
                "figure_id": "fig-001",
                "page_index": 0,
                "bbox": [100, 120, 220, 260],
                "image_path": image_rel,
                "context_above": "BHT overview paragraph.",
                "context_below": "Timing diagram explanation.",
            }
        ],
        "status": "Completed",
    }
    json_dir.joinpath("06_figures.json").write_text(
        json.dumps(figures_payload, indent=2), encoding="utf-8"
    )
    return figures_dir


@app.command()
def main(
    results: Path = typer.Option(
        Path("data/results/pipeline/smokes/06b_figure_describer"),
        "--results",
        "-o",
        help="Scratch pipeline directory for Stage 06b sanity.",
    )
) -> None:
    """Remove existing results directory and set up a new fixture."""
    if results.exists():
        shutil.rmtree(results)
    stage06_dir = _setup_fixture(results)

    try:
        out_path = run_figure_describer(
            stage_06_dir=stage06_dir, output_dir=results, skip_descriptions=True
        )
    except Exception as exc:  # pragma: no cover - smoke script
        typer.echo(f"Stage 06b execution failed: {exc}", err=True)
        raise typer.Exit(code=1)

    if not out_path.exists():
        typer.echo("06_figures.json missing after Stage 06b run", err=True)
        raise typer.Exit(code=2)
    data = json.loads(out_path.read_text(encoding="utf-8"))
    figures = data.get("figures") or []
    if not figures:
        typer.echo("Figures array empty after Stage 06b run", err=True)
        raise typer.Exit(code=3)
    typer.echo("OK: Stage 06b skip mode preserved figures JSON.")


if __name__ == "__main__":
    app()
