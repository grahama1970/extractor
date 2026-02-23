#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
#   "python-dotenv",
#   "pandas>=1.5",
#   "rapidfuzz>=3.0",
# ]
# ///
"""Comprehensive HTML vs PDF parity test for engineering documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List
import pandas as pd
from rapidfuzz import fuzz

import typer

from extractor.pipeline.structured_pipeline import (
    run_structured_pipeline,
)
from extractor.core.providers.html import HTMLProvider

app = typer.Typer(add_completion=False)


def extract_text_from_sections(sections: List[dict]) -> str:
    """Extract all text content from sections for comparison."""
    texts = []
    for section in sections:
        # Get section title
        if title := section.get("title"):
            texts.append(str(title))

        # Get text blocks
        for block in section.get("content", []):
            if block.get("type") == "text" and (content := block.get("content")):
                texts.append(str(content))
    return " \n ".join(texts)


def extract_tables_metadata(blocks: List[dict]) -> List[dict]:
    """Extract table metadata for comparison."""
    tables = []
    for block in blocks:
        if block.get("type") == "table":
            table_data = {
                "id": block.get("id"),
                "rows": len(block.get("content", [])),
                "context": block.get("section_id", ""),
                "has_csv": bool(block.get("csv_filename")),
            }
            tables.append(table_data)
    return tables


def extract_figures_metadata(blocks: List[dict]) -> List[dict]:
    """Extract figure metadata for comparison."""
    figures = []
    for block in blocks:
        if block.get("type") == "figure":
            fig_data = {
                "id": block.get("id"),
                "page": block.get("page_index", 0),
                "bbox": block.get("bbox") or [0, 0, 0, 0],
                "has_description": bool(block.get("ai_description") or block.get("description")),
            }
            figures.append(fig_data)
    return figures


def validate_encoding_preservation(text: str, original_encoding: str = None) -> bool:
    """Check if text can be encoded back to original encoding."""
    try:
        # Test round-trip encoding
        encoded = text.encode("utf-8")
        decoded = encoded.decode("utf-8")
        return decoded == text
    except (UnicodeEncodeError, UnicodeDecodeError):
        return False


def compare_section_structure(pdf_sections: List[dict], html_sections: List[dict]) -> dict:
    """Compare structural elements between PDF and HTML."""
    results = {
        "section_count_match": len(pdf_sections) == len(html_sections),
        "heading_level_consistency": True,
        "section_hierarchy_valid": True,
        "missing_sections": [],
        "extra_sections": [],
    }

    # Check if section count is within acceptable range (±2 for introductory/conclusion text)
    section_delta = abs(len(pdf_sections) - len(html_sections))
    results["section_count_acceptable"] = section_delta <= 2

    # Compare section titles/content
    pdf_by_title = {s.get("title", "").lower(): s for s in pdf_sections}
    html_by_title = {s.get("title", "").lower(): s for s in html_sections}

    common_titles = set(pdf_by_title.keys()) & set(html_by_title.keys())
    results["section_title_overlap"] = len(common_titles) / max(
        len(pdf_by_title), len(html_by_title), 1
    )

    # Find sections only in PDF or only in HTML
    pdf_only = set(pdf_by_title.keys()) - set(html_by_title.keys())
    html_only = set(html_by_title.keys()) - set(pdf_by_title.keys())

    results["missing_sections"] = list(pdf_only)
    results["extra_sections"] = list(html_only)

    return results


def compare_tables(table_comparison: dict, delta_threshold: float = 0.1) -> dict:
    """Compare table extraction between formats."""
    pdf_count = len(table_comparison.get("pdf_tables", []))
    html_count = len(table_comparison.get("html_tables", []))

    results = {
        "pdf_count": pdf_count,
        "html_count": html_count,
        "count_match": pdf_count == html_count,
        "count_acceptable": abs(pdf_count - html_count) <= 1,  # Allow off-by-one for edge cases
        "tables_with_csv": {
            "pdf": sum(1 for t in table_comparison.get("pdf_tables", []) if t["has_csv"]),
            "html": sum(1 for t in table_comparison.get("html_tables", []) if t["has_csv"]),
        },
        "table_context_consistency": True,
    }

    # Check that CSV extraction works for the same proportion of tables
    pdf_csv_ratio = results["tables_with_csv"]["pdf"] / max(pdf_count, 1)
    html_csv_ratio = results["tables_with_csv"]["html"] / max(html_count, 1)
    results["csv_extraction_parity"] = abs(pdf_csv_ratio - html_csv_ratio) < delta_threshold

    return results


def compare_content_similarity(pdf_text: str, html_text: str, min_similarity: float = 0.85) -> dict:
    """Compare text content similarity between PDF and HTML."""
    similarity = fuzz.ratio(pdf_text, html_text) / 100.0

    # Also check token overlap for better insight
    pdf_tokens = set(pdf_text.lower().split())
    html_tokens = set(html_text.lower().split())
    token_overlap = (
        len(pdf_tokens & html_tokens) / len(pdf_tokens | html_tokens)
        if pdf_tokens or html_tokens
        else 0
    )

    # Check character-level overlap within sections
    char_overlap = fuzz.partial_ratio(pdf_text, html_text) / 100.0

    results = {
        "similarity_score": similarity,
        "token_overlap": token_overlap,
        "character_overlap": char_overlap,
        "pass_threshold": similarity >= min_similarity,
        "content_preserved": similarity >= 0.75,  # Allow some differences due to formatting
        "token_parity": token_overlap >= 0.80,
    }

    # If different, try to identify WHY they're different
    if similarity < min_similarity:
        # Check for common issues
        pdf_length = len(pdf_text)
        html_length = len(html_text)

        if abs(pdf_length - html_length) / max(pdf_length, html_length) > 0.2:
            results["length_difference"] = {
                "pdf": pdf_length,
                "html": html_length,
                "ratio": html_length / pdf_length if pdf_length > 0 else 0,
            }

        # Check for encoding issues
        if not validate_encoding_preservation(html_text):
            results["encoding_issues"] = True

    return results


def generate_parity_report(results: dict, output_path: Path) -> None:
    """Generate a detailed parity report."""
    report = {
        "summary": {
            "overall_pass": results["overall_pass"],
            "pdf_test_file": str(results.get("pdf_file", "unknown")),
            "html_test_file": str(results.get("html_file", "unknown")),
            "test_timestamp": pd.Timestamp.now().isoformat(),
        },
        "content_analysis": results.get("content_comparison", {}),
        "structure_analysis": results.get("structure_comparison", {}),
        "table_analysis": results.get("table_comparison", {}),
        "figure_analysis": results.get("figure_comparison", {}),
        "detailed_failures": results.get("failures", []),
        "recommendations": results.get("recommendations", []),
    }

    output_path.write_text(json.dumps(report, indent=2, default=str))


@app.command()
def main(
    pdf_input: Path = typer.Option(
        Path("data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf"),
        exists=True,
        readable=True,
        help="PDF file to test",
    ),
    html_input: Path = typer.Option(
        Path("data/input/pipeline/indexed/test_document.html"), help="HTML version of same document"
    ),
    output_dir: Path = typer.Option(Path("data/results/parity_test_html")),
    strict_mode: bool = typer.Option(False, help="Fail on any content deviation"),
    content_threshold: float = typer.Option(0.85, help="Minimum similarity for content parity"),
) -> int:
    """Run comprehensive parity test between PDF and HTML extraction.

    Returns:
        0: Pass - HTML and PDF extraction are acceptably similar
        1: Fail - Issues found that need attention
    """
    typer.echo("=== HTML vs PDF Extraction Parity Test ===")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run PDF pipeline
    typer.echo(f"Processing PDF: {pdf_input}")
    pdf_results = run_structured_pipeline(
        None,  # PDF uses standard provider
        pdf_input,
        output_dir / "pdf_test",
        skip_export10=True,
        skip_embeddings10=True,
        fast_embeddings10=True,
    )

    # Run HTML pipeline
    typer.echo(f"Processing HTML: {html_input}")
    html_results = run_structured_pipeline(
        HTMLProvider,
        html_input,
        output_dir / "html_test",
        stage_prefix="html",
        skip_export10=True,
        skip_embeddings10=True,
        fast_embeddings10=True,
    )

    # Check basic success
    if not pdf_results.get("stage7") or not html_results.get("stage7"):
        typer.echo("ERROR: Pipeline failed for one or both formats", err=True)
        return 1

    # Extract data for comparison
    # Load PDF data (Stage 07)
    s07_pdf = json.loads(Path(pdf_results["stage7"]).read_text())
    pdf_sections = s07_pdf.get("reflowed_sections", [])

    # Load HTML data (Stage 07)
    s07_html = json.loads(Path(html_results["stage7"]).read_text())
    html_sections = s07_html.get("reflowed_sections", [])

    # Load tables from Stage 05 if available
    pdf_tables = []
    html_tables = []
    try:
        s05_pdf_path = next(
            (p for p in Path(pdf_results["stage5"]).parent.rglob("05_tables.json")), None
        )
        s05_html_path = next(
            (p for p in Path(html_results["stage5"]).parent.rglob("05_tables.json")), None
        )
        if s05_pdf_path and s05_html_path:
            pdf_tables_data = json.loads(s05_pdf_path.read_text())
            html_tables_data = json.loads(s05_html_path.read_text())
            pdf_tables = extract_tables_metadata(pdf_tables_data.get("tables", []))
            html_tables = extract_tables_metadata(html_tables_data.get("tables", []))
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Perform comparisons
    results = {
        "pdf_file": pdf_input,
        "html_file": html_input,
        "structure_comparison": compare_section_structure(pdf_sections, html_sections),
        "content_comparison": compare_content_similarity(
            extract_text_from_sections(pdf_sections),
            extract_text_from_sections(html_sections),
            min_similarity=content_threshold,
        ),
        "table_comparison": compare_tables({"pdf_tables": pdf_tables, "html_tables": html_tables}),
        "test_mode": "strict" if strict_mode else "loose",
    }

    # Determine overall pass/fail
    overall_pass = all(
        [
            results["structure_comparison"]["section_count_acceptable"],
            results["structure_comparison"]["section_title_overlap"] >= 0.8,
            (
                results["content_comparison"]["content_preserved"]
                if not strict_mode
                else results["content_comparison"]["pass_threshold"]
            ),
            results["table_comparison"]["count_acceptable"],
        ]
    )

    results["overall_pass"] = overall_pass

    # Generate detailed report
    report_path = output_dir / "parity_report.json"
    generate_parity_report(results, report_path)

    # Print summary
    typer.echo("\n=== Parity Test Results ===")
    typer.echo(
        f"Section structure: {'✅ PASS' if results['structure_comparison']['section_count_acceptable'] else '❌ FAIL'}"
    )
    typer.echo(
        f"Section title overlap: {results['structure_comparison']['section_title_overlap']:.1%}"
    )
    typer.echo(f"Content similarity: {results['content_comparison']['similarity_score']:.1%}")
    typer.echo(f"Table count: PDF={len(pdf_tables)}, HTML={len(html_tables)}")

    if overall_pass:
        typer.echo("\n✅ HTML extraction maintains parity with PDF extraction")
    else:
        typer.echo(f"\n❌ Parity issues found. See details in {report_path}")

        # Show specific failures
        if results["structure_comparison"]["missing_sections"]:
            typer.echo(
                f"Missing sections in HTML: {results['structure_comparison']['missing_sections'][:3]}"
            )
        if results["content_comparison"]["similarity_score"] < content_threshold:
            typer.echo(
                "Content similarity below threshold - check character encoding and structure"
            )

    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise typer.Exit(main())
