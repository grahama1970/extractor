#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv, find_dotenv


def build_cli() -> typer.Typer:
    app = typer.Typer(add_completion=False, help="Happy-path PDF extraction: one command, validated output.")

    @app.command()
    def run(
        pdf: Path = typer.Option(
            Path("data/input/pipeline/BHT_CV32A65X_marked.pdf"),
            exists=True,
            help="Input PDF (defaults to canonical BHT sample)",
        ),
        results: Path = typer.Option(
            Path("data/results/pipeline_happy"), help="Results directory"
        ),
        arango_db: str = typer.Option(
            os.getenv("ARANGO_DATABASE", "pdf_knowledge_base_test"),
            help="ArangoDB database name for this run",
        ),
        verbose: bool = typer.Option(False, "--verbose", help="Echo the full command"),
    ) -> None:
        """Run the modern function‑first PDF pipeline with deterministic toggles."""
        load_dotenv(find_dotenv() or None)
        env = os.environ.copy()
        env.setdefault("PYTHONPATH", str(Path.cwd() / "src"))
        env["ARANGO_DATABASE"] = arango_db

        results.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable,
            "-m",
            "extractor.pipeline.run_pipeline",
            "--pdf",
            str(pdf),
            "--out",
            str(results),
            "--summary-only",
            "--skip-fig-descriptions",
            "--stop-on-fail",
        ]

        if verbose:
            typer.echo("Running:\n" + " \\\n+\n  ".join(cmd))

        proc = subprocess.run(cmd, env=env)

        # Minimal run summary for quick triage
        try:
            import json

            summary = {
                "ok": proc.returncode == 0,
                "results": str(results),
                "arango_db": arango_db,
            }
            out = Path("scripts/artifacts/run_summary_happy.json")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(summary, indent=2))
            if verbose:
                typer.echo(f"Wrote run summary → {out}")
        except Exception:
            pass

        raise typer.Exit(proc.returncode)

    return app


def main() -> None:
    build_cli()()


if __name__ == "__main__":
    main()

