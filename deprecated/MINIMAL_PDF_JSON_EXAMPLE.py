#!/usr/bin/env python3
"""
MINIMAL PDF TO JSON EXTRACTION EXAMPLE

This is the simplest working code to extract PDFs to JSON using the extractor module.
Copy this to your project and adjust the imports.
"""

import os
import sys
import json
from pathlib import Path

# Environment setup (required)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

# Add extractor to path (adjust for your project)
# Option 1: If extractor is in current project
sys.path.insert(0, "src")

# Option 2: If extractor is in another location
# sys.path.insert(0, "/path/to/extractor/src")


def extract_pdf_to_json(pdf_path: str) -> dict:
    """
    Extract PDF to structured JSON format.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Dict with extracted content in ArangoDB-compatible format
    """
    # Import the unified extractor
    from extractor.unified_extractor_v2 import extract_to_unified_json
    
    # Extract the PDF
    result = extract_to_unified_json(pdf_path)
    
    return result


# Example usage
if __name__ == "__main__":
    # Your PDF file
    pdf_file = "example.pdf"  # Change this
    
    if not Path(pdf_file).exists():
        print(f"Please provide a valid PDF file. '{pdf_file}' not found.")
        sys.exit(1)
    
    # Extract
    print(f"Extracting {pdf_file}...")
    data = extract_pdf_to_json(pdf_file)
    
    # Show results
    sections = data.get('vertices', {}).get('sections', [])
    print(f"✓ Extracted {len(sections)} sections")
    
    # Save to file
    output_file = f"{Path(pdf_file).stem}_extracted.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Saved to {output_file}")
    
    # Show sample structure
    print("\nJSON Structure:")
    print("- vertices/")
    print("  - documents: Document metadata")
    print("  - sections: Extracted sections with hierarchy")
    print("  - entities: Named entities (if extracted)")
    print("- edges/")
    print("  - document_sections: Links documents to sections")
    print("  - section_hierarchy: Parent-child relationships")
    print("- original_content/")
    print("  - format: 'markdown'")
    print("  - content: Full markdown text")


"""
SETUP INSTRUCTIONS FOR OTHER PROJECTS
=====================================

1. Install dependencies:
   pip install pymupdf pydantic pillow torch transformers beautifulsoup4 python-docx

2. Copy the extractor source:
   - Copy the entire src/extractor directory to your project
   - Or install as a package if available

3. Use the code above

4. The output JSON format is designed for ArangoDB but works as standard JSON

COMMON ISSUES:
- ImportError: Make sure extractor is in your Python path
- Model downloads: First run will download Surya models (~1GB)
- Memory: Use a machine with at least 8GB RAM
- GPU: Optional but speeds up processing

For more control, you can also use:
- extractor.core.converters.pdf.convert_single_pdf() for markdown output
- extractor.core.convert.convert_pdf_to_json() for raw JSON blocks
"""