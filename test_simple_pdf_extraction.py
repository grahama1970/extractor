#!/usr/bin/env python3
"""
Simple test of PDF extraction without complex imports.

This script shows the minimal approach to extract PDFs.
"""

import os
import sys
import json
from pathlib import Path

# Setup environment
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_basic_import():
    """Test if we can import the conversion function."""
    try:
        from extractor.core.convert import convert_pdf_to_json
        print("✓ Successfully imported convert_pdf_to_json")
        return True
    except ImportError as e:
        print(f"✗ Failed to import: {e}")
        return False


def test_pdf_extraction():
    """Test actual PDF extraction."""
    from extractor.core.convert import convert_pdf_to_json
    
    # Find a test PDF
    test_pdfs = [
        "data/input/2505.03335v2.pdf",
        "test.pdf",
        "sample.pdf",
    ]
    
    pdf_path = None
    for test_pdf in test_pdfs:
        if Path(test_pdf).exists():
            pdf_path = test_pdf
            break
    
    if not pdf_path:
        print("\n✗ No test PDF found. Please provide a PDF path as argument:")
        print("  python test_simple_pdf_extraction.py your_document.pdf")
        return False
    
    print(f"\n✓ Found test PDF: {pdf_path}")
    print("  Converting to JSON...")
    
    try:
        # Convert with minimal options
        result = convert_pdf_to_json(
            pdf_path,
            max_pages=2,  # Limit for quick test
            disable_multiprocessing=True,
            disable_tqdm=True,
            use_llm=False
        )
        
        print(f"\n✓ Conversion successful!")
        print(f"  - Pages extracted: {len(result.get('children', []))}")
        print(f"  - Metadata: {result.get('metadata', {}).get('languages', 'N/A')}")
        
        # Show first page structure
        if result.get('children'):
            first_page = result['children'][0]
            block_types = {}
            for block in first_page.get('children', []):
                block_type = block.get('block_type', 'unknown')
                block_types[block_type] = block_types.get(block_type, 0) + 1
            
            print(f"\n  First page content:")
            for block_type, count in block_types.items():
                print(f"    - {block_type}: {count} blocks")
        
        # Save sample output
        output_file = "test_extraction_output.json"
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\n✓ Full output saved to: {output_file}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run tests."""
    print("PDF EXTRACTION TEST")
    print("=" * 50)
    
    # Check if PDF provided as argument
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        if Path(pdf_path).exists():
            print(f"Using provided PDF: {pdf_path}")
            
            from extractor.core.convert import convert_pdf_to_json
            result = convert_pdf_to_json(pdf_path, max_pages=5)
            
            output_file = f"{Path(pdf_path).stem}_extracted.json"
            with open(output_file, "w") as f:
                json.dump(result, f, indent=2)
            
            print(f"✓ Extracted to: {output_file}")
            print(f"✓ Pages: {len(result.get('children', []))}")
            return
        else:
            print(f"✗ PDF not found: {pdf_path}")
            return
    
    # Run basic tests
    if test_basic_import():
        test_pdf_extraction()
    
    print("\n" + "=" * 50)
    print("To use in another project:")
    print("1. Copy the src/extractor directory")
    print("2. Install dependencies: pip install pymupdf pydantic torch transformers")
    print("3. Use the code shown above")


if __name__ == "__main__":
    main()