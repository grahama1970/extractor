#!/usr/bin/env python3
"""Pipeline dispatcher that selects the appropriate flow per source format."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from extractor.core.providers.pdf import PdfProvider
from extractor.core.providers.registry import provider_from_filepath

from extractor.pipeline.structured_pipeline import (
    STRUCTURED_PIPELINES,
    run_structured_pipeline,
)
import subprocess
import sys


app = typer.Typer(add_completion=False, help="Dispatch extraction pipeline by format")


@app.command()
def run(
    input_path: Path = typer.Argument(..., exists=True, readable=True, help="Document to process"),
    results: Path = typer.Option(
        Path("data/results/pipeline"),
        file_okay=False,
        dir_okay=True,
        help="Results directory",
    ),
    skip_export10: bool = typer.Option(
        True,
        "--skip-export10/--no-skip-export10",
        help="Skip Arango export (applies to both PDF and HTML pipelines)",
    ),
    skip_embeddings10: bool = typer.Option(
        True,
        "--skip-embeddings10/--no-skip-embeddings10",
        help="Skip embedding computation during Stage 10 flattening",
    ),
    fast_embeddings10: bool = typer.Option(
        True,
        "--fast-embeddings10/--no-fast-embeddings10",
        help="Use deterministic hash embeddings when embeddings are enabled",
    ),
    offline: bool = typer.Option(
        False,
        "--offline/--no-offline",
        help="Offline mode for PDF pipeline (passed through to run_all)",
    ),
    arango_db: str = typer.Option(
        "pdf_knowledge_base_test",
        help="ArangoDB database to use for PDF pipeline runs",
    ),
    session: Optional[str] = typer.Option(None, help="Optional session id for PDF pipeline"),
    lean4_cli: Optional[str] = typer.Option(
        "python /home/graham/workspace/experiments/lean4/src/lean4_prover/cli_mini.py",
        help="Lean4 CLI path for PDF pipeline",
    ),
) -> None:
    """Run the appropriate pipeline based on the detected provider."""

    provider_cls = provider_from_filepath(str(input_path))

    if issubclass(provider_cls, PdfProvider):
        typer.echo("Detected PDF input; running modern PDF pipeline (run_pipeline).")
        cmd = [
            sys.executable,
            "-m",
            "extractor.pipeline.run_pipeline",
            "--pdf",
            str(input_path),
            "--out",
            str(results),
        ]
        proc = subprocess.run(cmd)
        raise typer.Exit(code=proc.returncode)

    for structured_cls, meta in STRUCTURED_PIPELINES.items():
        if issubclass(provider_cls, structured_cls):
            typer.echo(
                f"Detected {meta.format_name} input; running structured pipeline."
            )
            artifacts = run_structured_pipeline(
                structured_cls,
                input_path,
                results,
                stage_prefix=meta.stage_prefix,
                skip_export10=skip_export10,
                skip_embeddings10=skip_embeddings10,
                fast_embeddings10=fast_embeddings10,
            )
            for stage, path in artifacts.items():
                typer.echo(f"[{stage}] {path}")
            typer.echo(f"{meta.format_name} pipeline complete.")
            return

    typer.echo(
        f"Provider {provider_cls.__name__} is not yet wired into the dispatcher."
    )
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
