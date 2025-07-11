#!/usr/bin/env python3
"""
Original Marker-PDF to JSON - Proof of Concept

This uses the ORIGINAL marker package from https://github.com/datalab-to/marker
NOT the extractor fork.

Install with:
pip install marker-pdf
"""

import json
from pathlib import Path
import sys

# Original marker imports
from marker.convert import convert_single_pdf
from marker.models import load_all_models
from marker.output import save_json

def extract_pdf_to_json(pdf_path: str, output_path: str = None):
    """
    Extract PDF to JSON using original marker-pdf package.
    
    Args:
        pdf_path: Path to PDF file
        output_path: Optional output path for JSON (defaults to same name as PDF)
    """
    print(f"Loading marker models...")
    model_lst = load_all_models()
    
    print(f"Converting PDF: {pdf_path}")
    # Convert the PDF
    full_text, images, out_meta = convert_single_pdf(
        pdf_path,
        model_lst,
        max_pages=None,
        langs=None,
        batch_multiplier=2
    )
    
    # Determine output path
    if output_path is None:
        output_path = str(Path(pdf_path).with_suffix('.json'))
    
    # Save as JSON
    save_json(out_meta, images, output_path)
    
    print(f"✓ Conversion complete!")
    print(f"✓ Saved to: {output_path}")
    
    # Also return the data for inspection
    return full_text, images, out_meta


def main():
    # Get PDF path from command line or use default
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = "2505.03335v2.pdf"
    
    if not Path(pdf_path).exists():
        print(f"Error: PDF not found: {pdf_path}")
        return 1
    
    # Extract to JSON
    full_text, images, out_meta = extract_pdf_to_json(pdf_path)
    
    # Show summary
    print(f"\nExtraction Summary:")
    print(f"- Text length: {len(full_text):,} characters")
    print(f"- Images extracted: {len(images)}")
    print(f"- Metadata keys: {list(out_meta.keys())}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())