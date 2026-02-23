#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "ebooklib>=0.18",
#   "bs4>=4.12",
# ]
# ///
"""EPUB: when no TOC, build heading-based sections and ensure section-context exists."""

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
    epub_path = tmp_dir / "no_toc.epub"

    book = epub.EpubBook()
    book.set_title("No TOC Book")
    book.set_language("en")
    ch = epub.EpubHtml(title="Ch1", file_name="ch1.xhtml", lang="en")
    ch.content = """<html><body><h1>Chapter 1</h1><p>Para.</p></body></html>"""
    book.add_item(ch)
    # required nav artifacts
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", ch]
    book.toc = []  # explicit no TOC
    epub.write_epub(str(epub_path), book)

    meta = STRUCTURED_PIPELINES[EPUBProvider]
    artifacts = run_structured_pipeline(
        EPUBProvider,
        epub_path,
        tmp_dir,
        stage_prefix=meta.stage_prefix,
        skip_export10=True,
        skip_embeddings10=True,
        fast_embeddings10=True,
    )
    s07 = json.loads(Path(artifacts["stage07"]).read_text())
    sections = s07.get("reflowed_sections") or []
    if not sections:
        typer.echo("No sections in EPUB Stage 07 for no-TOC book.", err=True)
        raise typer.Exit(code=1)
    flat = json.loads(Path(artifacts["stage10_flattened"]).read_text())
    has_section_context = any(
        isinstance(obj, dict) and str(obj.get("section_id") or "") not in ("", "document-root")
        for obj in flat
    )
    if not has_section_context:
        typer.echo("No non-root section_id in Stage 10 flattened (EPUB no-TOC).", err=True)
        raise typer.Exit(code=1)
    typer.echo("EPUB no-TOC heading-based sectioning passed.")


if __name__ == "__main__":
    app()
