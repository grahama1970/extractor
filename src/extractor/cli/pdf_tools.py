#!/usr/bin/env python3
"""
PDF Tools CLI - Easy command-line interface for PDF image operations

This CLI provides simple commands that Claude can use to create snapshots,
section images, and table images from PDFs.

Usage:
    python pdf_tools.py snapshot --help
    python pdf_tools.py table-image --help
    python pdf_tools.py section-image --help
"""

import json
from pathlib import Path
from typing import List, Optional
import typer
from PIL import Image
from loguru import logger
import sys

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.extractor.core.processors.pdf_snapshot import PDFSnapshot
from src.extractor.core.processors.table_image_creator import TableImageCreator
from src.extractor.core.processors.semantic_section_processor import SemanticSectionProcessor

app = typer.Typer(help="PDF image tools for extraction pipeline")


def load_page_images(pdf_path: str) -> dict:
    """Load page images from PDF."""
    from pdf2image import convert_from_path

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        typer.echo(f"Error: PDF not found: {pdf_path}", err=True)
        raise typer.Exit(1)

    # Convert PDF pages to images
    images = convert_from_path(str(pdf_path), dpi=150)

    # Create page number to image mapping
    page_images = {i: img for i, img in enumerate(images)}

    return page_images


@app.command()
def snapshot(
    pdf_path: str = typer.Argument(..., help="Path to PDF file"),
    page: int = typer.Option(..., "--page", "-p", help="Page number (0-based)"),
    x0: float = typer.Option(..., help="Left coordinate"),
    y0: float = typer.Option(..., help="Top coordinate"),
    x1: float = typer.Option(..., help="Right coordinate"),
    y1: float = typer.Option(..., help="Bottom coordinate"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output image path"),
    label: Optional[str] = typer.Option(None, "--label", "-l", help="Label for the region"),
):
    """
    Take a snapshot of a specific region in a PDF.

    Example:
        python pdf_tools.py snapshot doc.pdf --page 0 --x0 100 --y0 200 --x1 500 --y1 400
    """
    typer.echo(f"Taking snapshot from {pdf_path} page {page}")

    # Load page images
    page_images = load_page_images(pdf_path)

    # Create snapshot
    snapper = PDFSnapshot()
    region = {"page": page, "bbox": [x0, y0, x1, y1], "label": label or f"Page {page} region"}

    img = snapper.snapshot(region, page_images, output_path=output)

    if img:
        if output:
            typer.echo(f"✓ Saved snapshot to: {output}")
        else:
            # Save to temp location
            temp_path = f"/tmp/snapshot_p{page}_{int(x0)}_{int(y0)}.png"
            img.save(temp_path)
            typer.echo(f"✓ Saved snapshot to: {temp_path}")
    else:
        typer.echo("✗ Failed to create snapshot", err=True)
        raise typer.Exit(1)


@app.command()
def snapshot_multi(
    pdf_path: str = typer.Argument(..., help="Path to PDF file"),
    regions_json: str = typer.Argument(..., help="JSON string or file with regions"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output image path"),
    stitch: bool = typer.Option(True, "--stitch/--no-stitch", help="Stitch regions together"),
):
    """
    Take snapshots of multiple regions and optionally stitch them.

    Regions JSON format:
        [{"page": 0, "bbox": [x0, y0, x1, y1], "label": "optional"}, ...]

    Example:
        python pdf_tools.py snapshot-multi doc.pdf '[{"page":0,"bbox":[100,200,500,400]}]'
    """
    typer.echo(f"Taking multiple snapshots from {pdf_path}")

    # Parse regions
    if regions_json.startswith("["):
        # Direct JSON
        regions = json.loads(regions_json)
    else:
        # File path
        with open(regions_json) as f:
            regions = json.load(f)

    # Load page images
    page_images = load_page_images(pdf_path)

    # Create snapshots
    snapper = PDFSnapshot()
    result = snapper.snapshot(regions, page_images, stitch=stitch, output_path=output)

    if result:
        if output:
            typer.echo(f"✓ Saved snapshot(s) to: {output}")
        else:
            # Save to temp
            if stitch and isinstance(result, Image.Image):
                temp_path = "/tmp/snapshot_stitched.png"
                result.save(temp_path)
                typer.echo(f"✓ Saved stitched snapshot to: {temp_path}")
            elif isinstance(result, list):
                for i, img in enumerate(result):
                    temp_path = f"/tmp/snapshot_{i}.png"
                    img.save(temp_path)
                typer.echo(f"✓ Saved {len(result)} snapshots to /tmp/")
    else:
        typer.echo("✗ Failed to create snapshots", err=True)
        raise typer.Exit(1)


@app.command()
def table_image(
    pdf_path: str = typer.Argument(..., help="Path to PDF file"),
    blocks_json: str = typer.Argument(..., help="JSON string or file with table blocks"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output image path"),
):
    """
    Create a merged image of table blocks that may span pages.

    Blocks should have: {"page": N, "bbox": [x0, y0, x1, y1], ...}

    Example:
        python pdf_tools.py table-image doc.pdf table_blocks.json -o table.png
    """
    typer.echo(f"Creating table image from {pdf_path}")

    # Parse blocks
    if blocks_json.startswith("[") or blocks_json.startswith("{"):
        blocks = json.loads(blocks_json)
    else:
        with open(blocks_json) as f:
            blocks = json.load(f)

    # Ensure it's a list
    if isinstance(blocks, dict):
        blocks = blocks.get("blocks", [blocks])

    # Load page images
    page_images = load_page_images(pdf_path)

    # Create table image
    creator = TableImageCreator()
    result = creator.create_table_images_from_blocks(blocks, page_images, output_dir=Path("/tmp"))

    if result.get("success"):
        img_path = result.get("image_path")
        if output and img_path:
            # Move to desired location
            Path(img_path).rename(output)
            typer.echo(f"✓ Saved table image to: {output}")
        else:
            typer.echo(f"✓ Saved table image to: {img_path}")

        typer.echo(f"  Pages: {result['pages']}")
        typer.echo(f"  Size: {result['size']}")
    else:
        typer.echo(f"✗ Failed: {result.get('error')}", err=True)
        raise typer.Exit(1)


@app.command()
def section_image(
    pdf_path: str = typer.Argument(..., help="Path to PDF file"),
    blocks_json: str = typer.Argument(..., help="JSON string or file with section blocks"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output image path"),
):
    """
    Create a merged image of a section that may span pages.

    Example:
        python pdf_tools.py section-image doc.pdf section_blocks.json
    """
    typer.echo(f"Creating section image from {pdf_path}")

    # Parse blocks
    if blocks_json.startswith("[") or blocks_json.startswith("{"):
        blocks = json.loads(blocks_json)
    else:
        with open(blocks_json) as f:
            blocks = json.load(f)

    # Ensure it's a list
    if isinstance(blocks, dict):
        blocks = blocks.get("blocks", [blocks])

    # Load page images
    page_images = load_page_images(pdf_path)

    # Create section image
    processor = SemanticSectionProcessor()
    img = processor.create_section_image(blocks, page_images)

    if img:
        output_path = output or "/tmp/section_image.png"
        img.save(output_path)
        typer.echo(f"✓ Saved section image to: {output_path}")
        typer.echo(f"  Size: {img.size}")
    else:
        typer.echo("✗ Failed to create section image", err=True)
        raise typer.Exit(1)


@app.command()
def quick_view(
    pdf_path: str = typer.Argument(..., help="Path to PDF file"),
    page: int = typer.Argument(..., help="Page number to view (0-based)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output path"),
):
    """
    Quick view of an entire PDF page.

    Example:
        python pdf_tools.py quick-view doc.pdf 0
    """
    typer.echo(f"Viewing page {page} of {pdf_path}")

    # Load page
    page_images = load_page_images(pdf_path)

    if page not in page_images:
        typer.echo(f"✗ Page {page} not found (PDF has {len(page_images)} pages)", err=True)
        raise typer.Exit(1)

    img = page_images[page]
    output_path = output or f"/tmp/page_{page}.png"
    img.save(output_path)

    typer.echo(f"✓ Saved page {page} to: {output_path}")
    typer.echo(f"  Size: {img.size}")


@app.command()
def list_commands():
    """List all available commands with examples."""
    typer.echo("PDF Tools - Available Commands:\n")

    typer.echo("1. snapshot - Extract a single region")
    typer.echo(
        "   python pdf_tools.py snapshot doc.pdf --page 0 --x0 100 --y0 200 --x1 500 --y1 400\n"
    )

    typer.echo("2. snapshot-multi - Extract multiple regions")
    typer.echo(
        '   python pdf_tools.py snapshot-multi doc.pdf \'[{"page":0,"bbox":[100,200,500,400]}]\'\n'
    )

    typer.echo("3. table-image - Create merged table image")
    typer.echo("   python pdf_tools.py table-image doc.pdf table_blocks.json\n")

    typer.echo("4. section-image - Create merged section image")
    typer.echo("   python pdf_tools.py section-image doc.pdf section_blocks.json\n")

    typer.echo("5. quick-view - View entire PDF page")
    typer.echo("   python pdf_tools.py quick-view doc.pdf 0\n")


if __name__ == "__main__":
    app()
