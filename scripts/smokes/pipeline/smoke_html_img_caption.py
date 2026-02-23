#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""HTML provider: img+caption adjacency mapping smoke.

Asserts that an <img> with an adjacent <p> (distance window 1) becomes a
Figure block with caption propagated to Stage 07 reflowed_sections.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from extractor.pipeline.structured_pipeline import STRUCTURED_PIPELINES, run_structured_pipeline
from extractor.core.providers.html import HTMLProvider

app = typer.Typer(add_completion=False)


@app.command()
def main(tmp_dir: Path = typer.Option(Path("data/results/structured_parity_smoke/html_synth"))):
    tmp_dir.mkdir(parents=True, exist_ok=True)
    html_path = tmp_dir / "adjacency.html"
    html_path.write_text(
        """
        <html><body>
          <h1>Doc</h1>
          <img src="x.png" alt="X"/>
          <p>My Caption</p>
        </body></html>
        """.strip(),
        encoding="utf-8",
    )

    meta = STRUCTURED_PIPELINES[HTMLProvider]
    artifacts = run_structured_pipeline(
        HTMLProvider,
        html_path,
        tmp_dir,
        stage_prefix=meta.stage_prefix,
        skip_export10=True,
        skip_embeddings10=True,
        fast_embeddings10=True,
    )

    s07 = json.loads(Path(artifacts["stage07"]).read_text())
    sections = s07.get("reflowed_sections") or []
    if not sections:
        typer.echo("No sections found in Stage 07 for synthetic HTML.", err=True)
        raise typer.Exit(code=1)
    figs = sections[0].get("figures") or []
    if not figs:
        typer.echo("No figures found in Stage 07 for synthetic HTML.", err=True)
        raise typer.Exit(code=1)
    cap = str(figs[0].get("caption") or "").strip()
    if cap != "My Caption":
        typer.echo(f"Caption mismatch: expected 'My Caption' got '{cap}'", err=True)
        raise typer.Exit(code=1)

    # Also ensure the caption paragraph wasn’t duplicated into reflowed_text
    rtext = sections[0].get("reflowed_text") or ""
    if "My Caption" in rtext:
        typer.echo("Caption text leaked into reflowed_text; expected it to be consumed.", err=True)
        raise typer.Exit(code=1)

    typer.echo("HTML img+caption adjacency mapping passed.")


if __name__ == "__main__":
    app()
