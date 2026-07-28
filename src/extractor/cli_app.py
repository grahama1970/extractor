"""Wheel-safe console entrypoint for canonical Extractor commands."""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path

import typer
from loguru import logger

from extractor import __version__
from extractor.application.extract_file import extract_file


app = typer.Typer(
    name="extractor",
    help="Extract supported files through the canonical Extractor facade",
    add_completion=False,
)


class OutputFormat(str, Enum):
    """Supported stdout presentation formats."""

    json = "json"
    markdown = "markdown"


@app.command("version")
def version() -> None:
    """Print the installed Extractor package version."""

    typer.echo(__version__)


@app.command()
def extract(
    input_file: Path = typer.Argument(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True, help="Input document"
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--out",
        "-o",
        help="Output directory for the extraction result and artifacts",
    ),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Disable optional network/model enrichment and use deterministic extraction only",
    ),
    output_format: OutputFormat = typer.Option(
        OutputFormat.json,
        "--format",
        help="Presentation format for stdout",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
) -> None:
    """Extract one supported file and emit an extractor.result.v1 envelope."""

    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    result = extract_file(input_file, output_dir=output_dir, offline=offline)
    if output_format is OutputFormat.markdown:
        typer.echo(
            "\n".join(
                [
                    f"# Extraction {result.status.value}",
                    "",
                    f"- schema: `{result.schema_version}`",
                    f"- source: `{result.source_path}`",
                    f"- output: `{result.output_dir}`",
                    f"- blocks: `{result.counts.blocks}`",
                    f"- artifacts: `{len(result.artifacts)}`",
                ]
            )
        )
    else:
        typer.echo(result.model_dump_json(indent=2))
    raise typer.Exit(0 if result.ok else 1)
