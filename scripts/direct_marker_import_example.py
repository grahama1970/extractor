#!/usr/bin/env python3
"""
Module: direct_marker_import_example.py
Description: Example showing how to directly import and use original marker-pdf from repos/marker

External Dependencies:
- marker-pdf: Original source in repos/marker
- loguru: https://pypi.org/project/loguru/

Sample Input:
>>> pdf_path = "example.pdf"

Expected Output:
>>> {"pages": [...], "metadata": {...}}

Example Usage:
>>> python direct_marker_import_example.py example.pdf
"""

import sys
import os
from pathlib import Path
import json
from loguru import logger

# CRITICAL: Add the original marker path BEFORE any imports
MARKER_REPO_PATH = "/home/graham/workspace/experiments/extractor/repos/marker"
sys.path.insert(0, MARKER_REPO_PATH)

# Now we can import the original marker
try:
    # These imports will come from repos/marker, NOT from extractor
    import marker
    from marker.converters.pdf import PdfConverter
    from marker.models import load_all_models
    from marker.output import output_as_json
    
    logger.success(f"Successfully imported marker from: {marker.__file__}")
except ImportError as e:
    logger.error(f"Failed to import marker: {e}")
    sys.exit(1)


def process_with_original_marker(pdf_path: str) -> dict:
    """Process a PDF using the original marker-pdf code"""
    logger.info(f"Processing {pdf_path} with original marker...")
    
    try:
        # Load the models
        logger.info("Loading marker models...")
        models = load_all_models()
        
        # Create the converter
        converter = PdfConverter(
            artifact_dict=models,
            processor_list=None,  # Use default processors
            renderer=output_as_json
        )
        
        # Process the PDF
        logger.info("Converting PDF...")
        rendered = converter(pdf_path)
        
        # Get the output
        result = rendered.output
        
        logger.success(f"Successfully processed PDF with original marker")
        return result
        
    except Exception as e:
        logger.error(f"Error processing with marker: {e}")
        return {"error": str(e)}


def compare_with_extractor(pdf_path: str) -> dict:
    """Compare original marker with extractor on the same PDF"""
    # First, get result from original marker
    logger.info("="*60)
    logger.info("Running ORIGINAL marker-pdf...")
    logger.info("="*60)
    
    marker_result = process_with_original_marker(pdf_path)
    
    # Now remove marker from path and import extractor
    sys.path.remove(MARKER_REPO_PATH)
    
    # Import extractor (which is the forked/modified marker)
    try:
        from extractor.converters.pdf import PdfConverter as ExtractorPdfConverter
        from extractor.models import load_all_models as load_extractor_models
        from extractor.output import output_as_json as extractor_output_as_json
        
        logger.info("="*60)
        logger.info("Running EXTRACTOR (modified marker)...")
        logger.info("="*60)
        
        # Load extractor models
        extractor_models = load_extractor_models()
        
        # Create extractor converter
        extractor_converter = ExtractorPdfConverter(
            artifact_dict=extractor_models,
            processor_list=None,
            renderer=extractor_output_as_json
        )
        
        # Process with extractor
        extractor_rendered = extractor_converter(pdf_path)
        extractor_result = extractor_rendered.output
        
        logger.success("Successfully processed PDF with extractor")
        
    except Exception as e:
        logger.error(f"Error processing with extractor: {e}")
        extractor_result = {"error": str(e)}
    
    # Compare results
    comparison = {
        "pdf_file": pdf_path,
        "marker_success": "error" not in marker_result,
        "extractor_success": "error" not in extractor_result,
        "marker_result": marker_result,
        "extractor_result": extractor_result
    }
    
    # Basic comparison metrics
    if comparison["marker_success"] and comparison["extractor_success"]:
        marker_pages = len(marker_result.get("pages", []))
        extractor_pages = len(extractor_result.get("pages", []))
        
        marker_text_len = sum(
            len(block.get("text", ""))
            for page in marker_result.get("pages", [])
            for block in page.get("blocks", [])
        )
        
        extractor_text_len = sum(
            len(block.get("text", ""))
            for page in extractor_result.get("pages", [])
            for block in page.get("blocks", [])
        )
        
        comparison["metrics"] = {
            "marker_pages": marker_pages,
            "extractor_pages": extractor_pages,
            "pages_match": marker_pages == extractor_pages,
            "marker_text_length": marker_text_len,
            "extractor_text_length": extractor_text_len,
            "text_length_ratio": extractor_text_len / marker_text_len if marker_text_len > 0 else 0
        }
        
        logger.info("="*60)
        logger.info("COMPARISON METRICS:")
        logger.info(f"Marker pages: {marker_pages}")
        logger.info(f"Extractor pages: {extractor_pages}")
        logger.info(f"Marker text length: {marker_text_len:,} chars")
        logger.info(f"Extractor text length: {extractor_text_len:,} chars")
        logger.info(f"Text ratio (extractor/marker): {comparison['metrics']['text_length_ratio']:.2f}")
        logger.info("="*60)
    
    return comparison


def main():
    """Main function demonstrating marker import and usage"""
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <pdf_path>")
        print("\nThis script demonstrates how to:")
        print("1. Import and use the original marker-pdf from repos/marker")
        print("2. Compare it with the extractor (forked marker)")
        print("3. Show metrics comparing both outputs")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    if not Path(pdf_path).exists():
        logger.error(f"PDF file not found: {pdf_path}")
        sys.exit(1)
    
    # Run comparison
    comparison = compare_with_extractor(pdf_path)
    
    # Save results
    output_file = f"marker_extractor_comparison_{Path(pdf_path).stem}.json"
    with open(output_file, 'w') as f:
        # Create a cleaner version for saving (without full content)
        save_data = {
            "pdf_file": comparison["pdf_file"],
            "marker_success": comparison["marker_success"],
            "extractor_success": comparison["extractor_success"],
            "metrics": comparison.get("metrics", {}),
            "marker_error": comparison["marker_result"].get("error") if "error" in comparison["marker_result"] else None,
            "extractor_error": comparison["extractor_result"].get("error") if "error" in comparison["extractor_result"] else None
        }
        json.dump(save_data, f, indent=2)
    
    logger.info(f"Comparison saved to: {output_file}")
    
    # Determine success
    if comparison["extractor_success"] and comparison.get("metrics", {}).get("text_length_ratio", 0) >= 0.8:
        logger.success("✅ Extractor produces comparable output to original marker")
        return 0
    else:
        logger.error("❌ Extractor output differs significantly from original marker")
        return 1


if __name__ == "__main__":
    sys.exit(main())