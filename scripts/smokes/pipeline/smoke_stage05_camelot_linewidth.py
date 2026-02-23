#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "camelot-py[cv]>=0.11",
#   "python-dotenv",
#   "typer>=0.12",
# ]
# ///
from __future__ import annotations

import sys
from pathlib import Path

import camelot
import typer
from dotenv import find_dotenv, load_dotenv


app = typer.Typer(
    add_completion=False, help="Inspect Stage 05 Camelot output with lattice/line_scale=15"
)


def _prepare_inputs(_: Path) -> Path:
    pdf_path = Path("data/input/pipeline/BHT CV32A65X_original.pdf")
    if not pdf_path.exists():
        raise SystemExit(f"Original PDF not found: {pdf_path}")
    return pdf_path


def run_smoke(results: Path, pages: str, line_scale: int) -> None:
    load_dotenv(find_dotenv(usecwd=True) or None)
    pdf_path = _prepare_inputs(results)

    typer.echo(
        f"Reading tables from {pdf_path} with lattice(line_scale={line_scale}) on pages {pages}"
    )
    tables = camelot.read_pdf(
        str(pdf_path),
        flavor="lattice",
        pages=pages,
        line_scale=line_scale,
        suppress_stdout=True,
    )
    if not tables:
        raise SystemExit("Camelot found no tables with the given configuration")

    issues = []
    for idx, table in enumerate(tables):
        df = table.df
        typer.echo(f"Table {idx} shape={df.shape}")
        if not df.empty:
            header = df.iloc[0].tolist()
            typer.echo(f"  header: {header}")
            fragments = [
                cell for cell in header if "\\n" in cell or "  " in cell or " " in cell.strip()
            ]
            if fragments:
                issues.append((idx, "header", fragments))
            body_first = df.iloc[1].tolist() if len(df) > 1 else []
            typer.echo(f"  first_row: {body_first}")
            body_bad = [
                cell for cell in body_first if "\\n" in cell or "  " in cell or " " in cell.strip()
            ]
            if body_bad:
                issues.append((idx, "row", body_bad))

    if issues:
        details = ", ".join(
            f"table {idx} {kind} contains split tokens {frags}" for idx, kind, frags in issues
        )
        raise SystemExit(
            f"Camelot lattice(line_scale={line_scale}) still yields fragmented text: {details}"
        )

    typer.echo("OK: Camelot extraction produced headers/rows without split tokens")


@app.command()
def main(
    results: Path = typer.Option(Path("data/results/pipeline"), "--results"),
    pages: str = typer.Option("1-2", help="Pages to sample for Camelot extraction"),
    line_scale: int = typer.Option(15, help="Camelot lattice line_scale value"),
):
    run_smoke(results, pages, line_scale)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        app()
    else:
        run_smoke(Path("data/results/pipeline"), "1-2", 15)
