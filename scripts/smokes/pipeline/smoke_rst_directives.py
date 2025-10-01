#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""RST: .. figure:: and grid table produce figures/tables in Stage 07."""

from __future__ import annotations

import json
from pathlib import Path
import typer

from extractor.pipeline.structured_pipeline import STRUCTURED_PIPELINES, run_structured_pipeline
from extractor.core.providers.rst import RSTProvider

app = typer.Typer(add_completion=False)


@app.command()
def main(tmp_dir: Path = typer.Option(Path("data/results/structured_parity_smoke/rst_synth"))):
    tmp_dir.mkdir(parents=True, exist_ok=True)
    rst_path = tmp_dir / "directives.rst"
    rst_path.write_text(
        """
Title
=====

.. figure:: https://example.com/x.png
   :alt: X

   An example figure.

=====  =====
A      B
=====  =====
1      2
=====  =====
        """.strip(),
        encoding="utf-8",
    )
    meta = STRUCTURED_PIPELINES[RSTProvider]
    artifacts = run_structured_pipeline(RSTProvider, rst_path, tmp_dir, stage_prefix=meta.stage_prefix, skip_export10=True, skip_embeddings10=True, fast_embeddings10=True)
    s07 = json.loads(Path(artifacts["stage07"]).read_text())
    sections = s07.get("reflowed_sections") or []
    assert sections, "No sections built"
    figs = sum(len(s.get("figures") or []) for s in sections)
    tabs = sum(len(s.get("tables") or []) for s in sections)
    if figs <= 0:
        typer.echo("No figures found from RST directives.", err=True)
        raise typer.Exit(code=1)
    if tabs <= 0:
        typer.echo("No tables found from RST directives.", err=True)
        raise typer.Exit(code=1)
    typer.echo("RST directives mapping passed.")


if __name__ == "__main__":
    app()

