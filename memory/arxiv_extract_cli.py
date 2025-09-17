#!/usr/bin/env python3
"""Convenience CLI for extracting ArXiv PDFs via the pipeline."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

import typer

def _download_arxiv_pdf(arxiv_id: str) -> Path:
    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    typer.echo(f"Downloading {url}")
    tmp_dir = Path(tempfile.mkdtemp(prefix="arxiv_pdf_"))
    pdf_path = tmp_dir / f"{arxiv_id}.pdf"
    try:
        with urllib.request.urlopen(url) as resp, pdf_path.open("wb") as f:
            f.write(resp.read())
    except urllib.error.HTTPError as exc:
        raise typer.BadParameter(f"Failed to fetch {url}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise typer.BadParameter(f"Failed to reach {url}: {exc.reason}") from exc
    return pdf_path


def build_cli() -> typer.Typer:
    app = typer.Typer(
        help="Download ArXiv PDFs and run the extraction pipeline",
        no_args_is_help=True,
    )

    @app.command()
    def run(
        pdf: Optional[Path] = typer.Option(
            None,
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Path to a local PDF",
        ),
        arxiv_id: Optional[str] = typer.Option(
            None,
            help=(
                "ArXiv identifier (e.g., 2203.00001). "
                "If provided, the PDF is downloaded automatically."
            ),
        ),
        results: Path = typer.Option(
            Path("data/results/pipeline"),
            help="Directory where pipeline results are stored",
        ),
        session: Optional[str] = typer.Option(
            None, help="Optional session identifier passed to the pipeline"
        ),
        lean4_cli: Optional[str] = typer.Option(
            "python /home/graham/workspace/experiments/lean4/src/lean4_prover/cli_mini.py",
            help="Lean4 CLI command for Stage 08",
        ),
    ) -> None:
        """Download (optional) and process a PDF through the full extraction pipeline."""

        if pdf is None and arxiv_id is None:
            raise typer.BadParameter("Either --pdf or --arxiv-id must be supplied")

        if pdf is not None and arxiv_id is not None:
            raise typer.BadParameter("Specify only one of --pdf or --arxiv-id")

        download_path: Optional[Path] = None
        if arxiv_id:
            download_path = _download_arxiv_pdf(arxiv_id)
            pdf_path = download_path
        else:
            pdf_path = pdf

        assert pdf_path is not None  # mypy guard
        results.mkdir(parents=True, exist_ok=True)
        typer.echo(f"Running extraction pipeline for {pdf_path}")

        session_value = session or f"arxiv-{pdf_path.stem}"
        cmd = [
            sys.executable,
            "src/extractor/pipeline/run_all.py",
            "run",
            "--pdf",
            str(pdf_path),
            "--results",
            str(results),
            "--session",
            session_value,
        ]

        if lean4_cli:
            cmd.extend(["--lean4-cli", lean4_cli])

        env = os.environ.copy()
        src_path = str(Path.cwd() / "src")
        if env.get("PYTHONPATH"):
            env["PYTHONPATH"] = os.pathsep.join([env["PYTHONPATH"], src_path])
        else:
            env["PYTHONPATH"] = src_path

        try:
            subprocess.run(cmd, check=True, env=env)
        except subprocess.CalledProcessError as exc:
            raise typer.Exit(code=exc.returncode) from exc
        typer.echo("Pipeline run complete. See logs and metrics for details.")

        if download_path:
            typer.echo(f"Downloaded PDF saved at: {download_path}")

    return app


def main() -> None:
    build_cli()()


if __name__ == "__main__":
    main()
