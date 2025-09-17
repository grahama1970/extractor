#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "ebooklib>=0.18",
# ]
# ///
"""EPUB: detect image and table in content; Stage 07 figures/tables present."""

from __future__ import annotations

import json
from pathlib import Path
import typer
from ebooklib import epub

from extractor.pipeline.structured_pipeline import STRUCTURED_PIPELINES, run_structured_pipeline
from extractor.core.providers.epub import EPUBProvider

app = typer.Typer(add_completion=False)


@app.command()
def main(tmp_dir: Path = typer.Option(Path("data/results/structured_parity_smoke/epub_synth"))):
    tmp_dir.mkdir(parents=True, exist_ok=True)
    epub_path = tmp_dir / "img_tbl.epub"
    book = epub.EpubBook()
    book.set_title("ImgTbl")
    book.set_language("en")
    c = epub.EpubHtml(title="C1", file_name="c1.xhtml", lang="en")
    c.content = """<html><body>
      <h1>Ch1</h1>
      <p>Para</p>
      <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII=" />
      <table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>
    </body></html>"""
    book.add_item(c)
    book.add_item(epub.EpubNcx()); book.add_item(epub.EpubNav())
    book.spine = ["nav", c]
    book.toc = []
    epub.write_epub(str(epub_path), book)

    meta = STRUCTURED_PIPELINES[EPUBProvider]
    artifacts = run_structured_pipeline(EPUBProvider, epub_path, tmp_dir, stage_prefix=meta.stage_prefix, skip_export10=True, skip_embeddings10=True, fast_embeddings10=True)
    s07 = json.loads(Path(artifacts["stage07"]).read_text())
    secs = s07.get("reflowed_sections") or []
    assert secs, "No sections built"
    total_figs = sum(len(s.get("figures") or []) for s in secs)
    total_tbls = sum(len(s.get("tables") or []) for s in secs)
    if total_figs <= 0:
        typer.echo("No figures detected in EPUB Stage 07.", err=True)
        raise typer.Exit(code=1)
    if total_tbls <= 0:
        typer.echo("No tables detected in EPUB Stage 07.", err=True)
        raise typer.Exit(code=1)
    typer.echo("EPUB image+table detection passed.")


if __name__ == "__main__":
    app()
