#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
from __future__ import annotations

import tarfile
from pathlib import Path
import time
import typer

app = typer.Typer(add_completion=False)


@app.command()
def main(
    slug: str = typer.Option(..., help="Slug used in annotated file name (annotated_<slug>.pdf)"),
    artifacts_dir: Path = typer.Option(Path("scripts/artifacts"), help="Artifacts root"),
    output: Path = typer.Option(None, help="Output tar.gz (default under scripts/artifacts)"),
) -> None:
    """Generate a tar.gz archive from annotated PDF files in the artifacts directory."""
    artifacts_dir = artifacts_dir.resolve()
    pdf = artifacts_dir / f"annotated_{slug}.pdf"
    pages_dir = artifacts_dir / f"annotated_{slug}.pdf_pages"
    ann_dir = artifacts_dir / f"annotated_{slug}_ann"
    if not pdf.exists():
        raise SystemExit(f"Annotated PDF not found: {pdf}")
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    if output is None:
        output = artifacts_dir / f"annotated_{slug}_{stamp}.tar.gz"
    output.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(output, "w:gz") as tar:
        tar.add(pdf, arcname=pdf.name)
        if pages_dir.exists():
            tar.add(pages_dir, arcname=pages_dir.name)
        if ann_dir.exists():
            tar.add(ann_dir, arcname=ann_dir.name)
    print(str(output))


if __name__ == "__main__":
    app()
