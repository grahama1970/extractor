#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pymupdf>=1.23.0",
#   "typer>=0.12.3",
# ]
# ///
from __future__ import annotations

import sys
from pathlib import Path
import typer

app = typer.Typer(add_completion=False, help="Remove all annotations from a PDF (writes a new file)")


@app.command()
def main(
    src: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True, help="Input PDF with annotations"),
    out: Path | None = typer.Option(None, "--out", "-o", help="Output PDF (default: <stem>_noannots.pdf beside input)"),
    remove_links: bool = typer.Option(False, "--remove-links/--keep-links", help="Also remove link annotations (URIs)")
):
    try:
        import fitz  # PyMuPDF
    except Exception as e:
        typer.secho(f"PyMuPDF not available: {e}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2)

    dst = out or src.with_name(f"{src.stem}_noannots.pdf")
    if dst.resolve() == src.resolve():
        typer.secho("Refusing to overwrite the source file; choose a different --out.", fg=typer.colors.RED)
        raise typer.Exit(3)

    doc = fitz.open(str(src))
    removed = 0
    with doc:
        for page in doc:
            # Remove standard annotations
            annots = list(page.annots() or [])
            for a in annots:
                page.delete_annot(a)
                removed += 1
            if remove_links:
                # Remove link annotations (link rectangles)
                for l in list(page.get_links() or []):
                    try:
                        rect = l.get("from")
                        if rect is not None:
                            page.add_redact_annot(fitz.Rect(rect))
                    except Exception:
                        pass
                try:
                    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
                except Exception:
                    pass
        doc.save(str(dst))
    typer.echo(f"OK: removed {removed} annotations → {dst}")


if __name__ == "__main__":
    app()

