#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "duckdb>=0.9",
# ]
# ///
from __future__ import annotations

import shutil
from pathlib import Path

import duckdb
import typer

from extractor.pipeline.steps.s10_markdown_exporter import run as run_markdown_exporter

app = typer.Typer(
    add_completion=False,
    help="Smoke: Stage 10 markdown exporter renders deterministic markdown.",
)


def _build_db(db_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    con.execute(
        """
        CREATE TABLE sections (
            id VARCHAR,
            title VARCHAR,
            page_start INTEGER,
            llm_summary VARCHAR
        )
        """
    )
    con.execute(
        "INSERT INTO sections VALUES ('s1', '4.1.5 Branch History Table', 1, 'Tracks last eight outcomes.')"
    )
    con.execute(
        """
        CREATE TABLE merged_content (
            id VARCHAR,
            section_id VARCHAR,
            type VARCHAR,
            content VARCHAR,
            sort_order INTEGER,
            asset_id VARCHAR
        )
        """
    )
    con.execute(
        """
        INSERT INTO merged_content VALUES
        ('c1', 's1', 'text', 'The CPU shall record branch outcomes.', 100, NULL),
        ('c2', 's1', 'requirement', NULL, 200, 'req-1'),
        ('c3', 's1', 'table', NULL, 300, 'tbl-1'),
        ('c4', 's1', 'figure', NULL, 400, 'fig-1')
        """
    )
    con.execute(
        """
        CREATE TABLE requirements (
            id VARCHAR,
            req_id VARCHAR,
            text VARCHAR,
            citation_snippet VARCHAR,
            type VARCHAR,
            is_conditional BOOLEAN,
            metadata_json VARCHAR
        )
        """
    )
    con.execute(
        """
        INSERT INTO requirements VALUES
        ('req-1', 'REQ-BHT-1', 'The CPU shall record the last eight branch outcomes.', 'The CPU shall record...', 'functional', False, '{"page":1,"bbox":[0,0,1,1],"bbox_source":"block"}')
        """
    )
    con.execute(
        """
        CREATE TABLE tables (
            id VARCHAR,
            csv_data VARCHAR,
            llm_title VARCHAR,
            llm_description VARCHAR
        )
        """
    )
    con.execute(
        """
        INSERT INTO tables VALUES
        ('tbl-1', 'Cycle,Action\n1,Read\n2,Write', 'INFERRED: Branch Table', 'Records branch outcomes.')
        """
    )
    con.execute(
        """
        CREATE TABLE figures (
            id VARCHAR,
            image_path VARCHAR,
            llm_title VARCHAR,
            llm_description VARCHAR
        )
        """
    )
    con.execute(
        """
        INSERT INTO figures VALUES
        ('fig-1', 'figures/fig-1.png', 'Pipeline Diagram', 'Shows CPU pipeline stages.')
        """
    )
    con.close()


@app.command()
def main(
    results: Path = typer.Option(
        Path("data/results/pipeline/smokes/10_markdown_exporter"),
        "--results",
        "-o",
        help="Scratch directory for Stage 10 markdown sanity.",
    )
) -> None:
    if results.exists():
        shutil.rmtree(results)
    results.mkdir(parents=True, exist_ok=True)
    db_path = results / "markdown_sanity.duckdb"
    _build_db(db_path)

    try:
        run_markdown_exporter(db_path, output_dir=results)
    except Exception as exc:  # pragma: no cover - smoke script
        typer.echo(f"Stage 10 markdown execution failed: {exc}", err=True)
        raise typer.Exit(code=1)

    doc_path = results / "10_markdown_exporter" / "markdown_output" / "full_document.md"
    if not doc_path.exists():
        typer.echo("Markdown export missing full_document.md", err=True)
        raise typer.Exit(code=2)
    text = doc_path.read_text(encoding="utf-8")
    if "REQ-BHT-1" not in text or "INFERRED: Branch Table" not in text:
        typer.echo("Markdown export missing requirement or table content", err=True)
        raise typer.Exit(code=3)
    typer.echo("OK: Stage 10 markdown exporter produced full_document.md")


if __name__ == "__main__":
    app()
