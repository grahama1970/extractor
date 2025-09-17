#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""XML: sect/title mapping produces sections in Stage 07."""

from __future__ import annotations

import json
from pathlib import Path
import typer

from extractor.pipeline.structured_pipeline import STRUCTURED_PIPELINES, run_structured_pipeline
from extractor.core.providers.xml import XMLProvider

app = typer.Typer(add_completion=False)


@app.command()
def main(tmp_dir: Path = typer.Option(Path("data/results/structured_parity_smoke/xml_synth"))):
    tmp_dir.mkdir(parents=True, exist_ok=True)
    xml_path = tmp_dir / "sect.xml"
    xml_path.write_text(
        """
        <root>
          <sect1>
            <title>Ch1</title>
            <para>Hello</para>
          </sect1>
        </root>
        """.strip(),
        encoding="utf-8",
    )
    meta = STRUCTURED_PIPELINES[XMLProvider]
    artifacts = run_structured_pipeline(XMLProvider, xml_path, tmp_dir, stage_prefix=meta.stage_prefix, skip_export10=True, skip_embeddings10=True, fast_embeddings10=True)
    s07 = json.loads(Path(artifacts["stage07"]).read_text())
    sections = s07.get("reflowed_sections") or []
    if not sections:
        typer.echo("No sections built for sect/title XML synthetic.", err=True)
        raise typer.Exit(code=1)
    typer.echo("XML sect/title → sections passed.")


if __name__ == "__main__":
    app()

