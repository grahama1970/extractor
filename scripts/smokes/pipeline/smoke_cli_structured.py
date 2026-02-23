#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""CLI smoke: extract (structured formats) writes Stage 07/10 artifacts."""

from __future__ import annotations

import subprocess
from pathlib import Path
import sys
import json
import typer

app = typer.Typer(add_completion=False)


def _assert_stage_paths(root: Path, stem: str, stage07_dir: str) -> None:
    s07 = root / stem / stage07_dir / "json_output" / "07_reflowed.json"
    s10 = root / stem / "10_arangodb_exporter" / "json_output" / "10_flattened_data.json"
    if not s07.exists() or not s10.exists():
        raise AssertionError(f"Missing Stage outputs: {s07} or {s10}")
    # sanity load
    json.loads(s07.read_text())
    json.loads(s10.read_text())


@app.command()
def main(
    html_path: Path = typer.Option(
        Path("data/results/pipeline/01_annotation_processor/BHT_CV32A65X_marked_clean.html"),
        exists=True,
    ),
    output_dir: Path = typer.Option(Path("data/results/cli_smokes/structured")),
):
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "src.cli", "extract", str(html_path), str(output_dir)]
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        typer.echo("CLI structured extract failed.", err=True)
        raise typer.Exit(code=1)
    _assert_stage_paths(output_dir, html_path.stem, "07_html_ingest")
    typer.echo("CLI structured smoke passed.")


if __name__ == "__main__":
    app()
