#!/usr/bin/env python3
"""
Simple proof of concept for PDF to JSON conversion using extractor.

This script demonstrates the minimal setup needed to convert a PDF to structured JSON.
"""

import json
import sys
from pathlib import Path

# Add the src directory to Python path to ensure imports work
sys.path.insert(0, str(Path(__file__).parent / "src"))

from extractor.core.convert import convert_pdf_to_json


def simple_pdf_to_json(pdf_path: str, output_path: str = None):
    """
    Convert a PDF file to structured JSON.
    
    Args:
        pdf_path: Path to the PDF file
        output_path: Optional path to save JSON output (if not provided, prints to stdout)
    """
    # Check if PDF exists
    if not Path(pdf_path).exists():
        print(f"Error: PDF file not found: {pdf_path}")
        return None
    
    try:
        print(f"Converting PDF: {pdf_path}")
        
        # Convert PDF to JSON with minimal config
        json_data = convert_pdf_to_json(
            pdf_path,
            # Optional configuration overrides
            max_pages=None,  # Process all pages
            disable_multiprocessing=True,
            disable_tqdm=True,
            use_llm=False  # Disable LLM enhancement for speed
        )
        
        # Save or print the JSON
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            print(f"JSON saved to: {output_path}")
        else:
            print("\nJSON Output:")
            print(json.dumps(json_data, indent=2, ensure_ascii=False))
        
        return json_data
        
    except Exception as e:
        print(f"Error during conversion: {e}")
        import traceback
        traceback.print_exc()
        return None


def working_usage():
    """Demonstrate proper usage of the PDF to JSON converter."""
    # Example with a test PDF
    test_pdf = "data/input/2505.03335v2.pdf"  # Update this path
    output_json = "output_poc.json"
    
    if Path(test_pdf).exists():
        result = simple_pdf_to_json(test_pdf, output_json)
        if result:
            print(f"\nSuccess! Converted {len(result.get('children', []))} pages")
            print(f"Metadata: {result.get('metadata', {})}")
    else:
        print(f"Please provide a valid PDF path. Test file not found: {test_pdf}")
        print("\nUsage: python simple_pdf_to_json_poc.py <pdf_path> [output_json_path]")


def debug_function():
    """Debug function for testing with command line arguments."""
    if len(sys.argv) < 2:
        print("Usage: python simple_pdf_to_json_poc.py <pdf_path> [output_json_path]")
        print("\nRunning working_usage() instead...")
        working_usage()
        return
    
    pdf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    simple_pdf_to_json(pdf_path, output_path)


if __name__ == "__main__":
    """
    Run with:
    - python simple_pdf_to_json_poc.py                    # Runs working_usage()
    - python simple_pdf_to_json_poc.py debug              # Runs debug mode
    - python simple_pdf_to_json_poc.py <pdf_path>         # Convert and print JSON
    - python simple_pdf_to_json_poc.py <pdf_path> <output> # Convert and save JSON
    """
    mode = sys.argv[1] if len(sys.argv) > 1 else "working"
    
    if mode == "debug" or (len(sys.argv) > 1 and mode.endswith('.pdf')):
        debug_function()
    else:
        working_usage()