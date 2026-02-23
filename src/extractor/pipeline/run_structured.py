#!/usr/bin/env python3
"""
run_structured.py - Entry point for structured format extraction (HTML, MD, DOCX, XML, etc.)

This pipeline bypasses PDF-specific stages (S01-S06) and feeds directly into S07+.

Flow:
    Format Detection → Provider → UnifiedDocument → UnifiedAdapter → S07+
"""
import argparse
import json
import sys
from pathlib import Path

from loguru import logger

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from extractor.core.schema.unified_document import UnifiedDocument  # noqa: E402
from extractor.pipeline.adapters.unified_adapter import UnifiedAdapter  # noqa: E402


def get_provider(filepath: Path):
    """Get appropriate provider based on file extension.

    Delegates to the central provider registry which handles 49+ extensions
    with MIME-type fallback and HTML sniffing.  PDF files are excluded here
    because they have their own pipeline path (S00-S06).
    """
    from extractor.core.providers.registry import provider_from_filepath
    from extractor.core.providers.pdf import PdfProvider

    provider_cls = provider_from_filepath(str(filepath))
    if provider_cls is PdfProvider:
        raise ValueError(
            f"Unsupported format for structured pipeline: {filepath.suffix} "
            "(PDF files use the main pipeline, not run_structured)"
        )
    return provider_cls()


def _synthesize_profile(source_path: Path, unified_doc: "UnifiedDocument", output_dir: Path) -> None:
    """Write a minimal 00_profile_detector/profile.json from UnifiedDocument metadata.

    This gives non-PDF documents the same S00-style metadata that the scoring,
    sampling, escalation, and ArangoDB export pipelines expect.
    """
    blocks = unified_doc.blocks or []
    pages = {getattr(b, "metadata", None) and getattr(b.metadata, "page_number", 0) or 0 for b in blocks}
    page_count = max(pages) if pages else 1

    # Count block types — BlockType is a str enum so compare with lowercase values
    tables = sum(1 for b in blocks if getattr(b, "type", None) == "table")
    figures = sum(1 for b in blocks if getattr(b, "type", None) == "figure")
    sections = sum(1 for b in blocks if getattr(b, "type", None) in ("heading", "section_header"))
    text_blocks = sum(1 for b in blocks if getattr(b, "type", None) == "paragraph")
    has_formulas = any(getattr(b, "type", None) == "equation" for b in blocks)

    suffix = source_path.suffix.lower().lstrip(".")
    file_size_mb = 0.0
    try:
        file_size_mb = round(source_path.stat().st_size / (1024 * 1024), 2)
    except OSError:
        pass

    profile = {
        "source_file": str(source_path),
        "format": suffix,
        "page_count": page_count,
        "file_size_mb": file_size_mb,
        "domain": "structured",
        "detected_preset": f"{suffix}_structured",
        "is_scanned": False,
        "layout": {"columns": 1},
        "elements": {
            "tables": tables > 0,
            "figures": figures > 0,
            "formulas": has_formulas,
            "requirements": False,
            "estimated_table_count": tables,
            "estimated_figure_count": figures,
            "estimated_section_count": sections,
            "text_block_count": text_blocks,
        },
        "context": {
            "total_blocks": len(blocks),
            "format_type": suffix,
        },
    }

    profile_dir = output_dir / "00_profile_detector"
    profile_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profile_dir / "profile.json"
    profile_path.write_text(json.dumps(profile, indent=2))
    logger.info(f"Wrote profile.json: {page_count} pages, {tables} tables, {figures} figures, {sections} sections")


def run_structured_pipeline(source_path: Path, output_dir: Path, run_s07_plus: bool = True) -> bool:
    """
    Run the structured format pipeline.

    Args:
        source_path: Path to source file (HTML, MD, DOCX, etc.)
        output_dir: Directory for output artifacts
        run_s07_plus: Whether to continue with S07+ stages

    Returns:
        True if successful
    """
    source_path = Path(source_path).resolve()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Running structured pipeline: {source_path.name}")

    # Step 1: Get appropriate provider
    try:
        provider = get_provider(source_path)
        logger.info(f"Using provider: {provider.__class__.__name__}")
    except ValueError as e:
        logger.error(str(e))
        return False

    # Step 2: Extract to UnifiedDocument
    logger.info("Extracting to UnifiedDocument...")
    try:
        unified_doc: UnifiedDocument = provider.extract_document(source_path)
        logger.info(f"Extracted {len(unified_doc.blocks)} blocks")
    except Exception as e:
        logger.error(f"Provider extraction failed: {e}")
        return False

    # Step 2b: Synthesize S00-compatible profile.json for scoring/ArangoDB
    try:
        _synthesize_profile(source_path, unified_doc, output_dir)
    except Exception as e:
        logger.warning(f"Profile synthesis failed (non-fatal): {e}")

    # Step 3: Adapt to pipeline artifacts
    logger.info("Running UnifiedAdapter...")
    try:
        adapter = UnifiedAdapter(unified_doc, output_dir)
        adapter.write_artifacts()
        logger.info("Artifacts written successfully")
    except Exception as e:
        logger.error(f"Adapter failed: {e}")
        return False

    # Step 4: Run S07+ (optional)
    if run_s07_plus:
        logger.info("Invoking S07+ stages...")

        # Locate adapter artifacts (UnifiedAdapter writes into stage subdirs)
        sections_file = output_dir / "04_section_builder" / "json_output" / "04_sections.json"
        tables_file = output_dir / "05_table_extractor" / "json_output" / "05_tables.json"
        figures_file = output_dir / "06_figure_extractor" / "json_output" / "06_figures.json"

        if not sections_file.exists():
            logger.warning(f"{sections_file} not found — skipping S07+")
        else:
            # S07: JSON Assembler — builds assembled_content.json from adapter artifacts
            try:
                from extractor.pipeline.steps.s07_json_assembler import run_assemble_corpus

                assembled_path = output_dir / "07_assembled" / "assembled_content.json"
                run_assemble_corpus(
                    output_json_path=assembled_path,
                    sections_json=sections_file,
                    tables_json=tables_file if tables_file.exists() else None,
                    figures_json=figures_file if figures_file.exists() else None,
                    source_pdf=str(source_path),
                )
                logger.info(f"S07 assembled: {assembled_path}")
            except Exception as e:
                logger.warning(f"S07 JSON assembler failed (non-fatal): {e}")
                assembled_path = None

            # S11: Structural JSON Exporter — produces structural.json for scoring
            if assembled_path and assembled_path.exists():
                try:
                    from extractor.pipeline.steps.s11_json_exporter import run as run_s11

                    run_s11(input_path=output_dir)
                    s11_out = output_dir / "11_json_exporter" / "structural.json"
                    if s11_out.exists():
                        logger.info(f"S11 structural JSON: {s11_out}")
                    else:
                        logger.warning("S11 ran but structural.json not found")
                except Exception as e:
                    logger.warning(f"S11 JSON exporter failed (non-fatal): {e}")

            # S10: Markdown Exporter (lightweight, deterministic)
            if assembled_path and assembled_path.exists():
                try:
                    from extractor.pipeline.steps.s10_markdown_exporter import run as run_s10_md

                    run_s10_md(input_path=output_dir)
                    logger.info("S10 markdown export complete")
                except Exception as e:
                    logger.warning(f"S10 markdown exporter failed (non-fatal): {e}")

    logger.info("Structured pipeline complete")
    return True


def main():
    parser = argparse.ArgumentParser(description="Structured Format Pipeline")
    parser.add_argument("source", type=Path, help="Source file (HTML, MD, DOCX, etc.)")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("data/results/structured"),
        help="Output directory",
    )
    parser.add_argument("--skip-s07", action="store_true", help="Skip S07+ stages")
    args = parser.parse_args()

    success = run_structured_pipeline(
        source_path=args.source, output_dir=args.output, run_s07_plus=not args.skip_s07
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
