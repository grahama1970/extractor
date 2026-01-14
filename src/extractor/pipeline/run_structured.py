#!/usr/bin/env python3
"""
run_structured.py - Entry point for structured format extraction (HTML, MD, DOCX, XML, etc.)

This pipeline bypasses PDF-specific stages (S01-S06) and feeds directly into S07+.

Flow:
    Format Detection → Provider → UnifiedDocument → UnifiedAdapter → S07+
"""
import argparse
import sys
from pathlib import Path
from typing import Optional

from loguru import logger

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from extractor.core.schema.unified_document import UnifiedDocument
from extractor.pipeline.adapters.unified_adapter import UnifiedAdapter


# Provider imports
def get_provider(filepath: Path):
    """Get appropriate provider based on file extension."""
    suffix = filepath.suffix.lower()
    
    if suffix in [".html", ".htm"]:
        from extractor.core.providers.html import HTMLProvider
        return HTMLProvider()
    elif suffix in [".md", ".markdown"]:
        from extractor.core.providers.markdown import MarkdownProvider
        return MarkdownProvider()
    elif suffix == ".docx":
        from extractor.core.providers.docx import DocxProvider
        return DocxProvider()
    elif suffix == ".pptx":
        from extractor.core.providers.pptx import PptxProvider
        return PptxProvider()
    elif suffix == ".xml":
        from extractor.core.providers.xml import XMLProvider
        return XMLProvider()
    elif suffix == ".rst":
        from extractor.core.providers.rst import RSTProvider
        return RSTProvider()
    elif suffix == ".epub":
        from extractor.core.providers.epub import EpubProvider
        return EpubProvider()
    elif suffix in [".csv", ".xlsx", ".xls"]:
        from extractor.core.providers.spreadsheet import SpreadsheetProvider
        return SpreadsheetProvider()
    else:
        raise ValueError(f"Unsupported format: {suffix}")


def run_structured_pipeline(
    source_path: Path,
    output_dir: Path,
    run_s07_plus: bool = True
) -> bool:
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
        # Import and run S07-S10
        # For now, just verify artifacts exist
        sections_file = output_dir / "04_sections.json"
        if sections_file.exists():
            logger.info(f"✅ {sections_file.name} created")
        else:
            logger.warning(f"⚠️ {sections_file.name} not found")
            
        # TODO: Invoke actual S07+ steps
        # This would call run_pipeline.py with --start-step 7
        
    logger.info("Structured pipeline complete")
    return True


def main():
    parser = argparse.ArgumentParser(description="Structured Format Pipeline")
    parser.add_argument("source", type=Path, help="Source file (HTML, MD, DOCX, etc.)")
    parser.add_argument("-o", "--output", type=Path, default=Path("data/results/structured"),
                        help="Output directory")
    parser.add_argument("--skip-s07", action="store_true", help="Skip S07+ stages")
    args = parser.parse_args()
    
    success = run_structured_pipeline(
        source_path=args.source,
        output_dir=args.output,
        run_s07_plus=not args.skip_s07
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
