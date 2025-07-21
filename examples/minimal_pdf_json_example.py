#!/usr/bin/env python3
"""
Minimal example showing how to convert PDF to JSON using extractor's core components.

This demonstrates the exact imports and setup needed for another project.
"""

import json
import os
import sys
from pathlib import Path

# CRITICAL: Set environment variables BEFORE imports
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

# Add source to path (adjust this for your project structure)
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Direct imports approach (what the core convert.py does internally)
from extractor.core.converters.pdf import PdfConverter
from extractor.core.renderers.json import JSONRenderer
from extractor.core.models import create_model_dict


def convert_pdf_direct(pdf_path: str) -> dict:
    """
    Direct conversion using the core classes (mimics convert.py internally).
    
    This shows exactly what convert_pdf_to_json does under the hood.
    """
    # Create model dictionary (handles model weights)
    models = create_model_dict()
    
    # Configure the converter
    config = {
        "disable_multiprocessing": True,
        "disable_tqdm": True,
        "use_llm": False,  # Disable LLM for speed
    }
    
    # Create converter with JSON renderer
    converter = PdfConverter(
        artifact_dict=models,
        renderer="extractor.core.renderers.json.JSONRenderer",
        config=config
    )
    
    # Convert PDF (returns JSONOutput pydantic model)
    json_output = converter(pdf_path)
    
    # Convert to plain dict
    return json_output.model_dump()


# Alternative: Use the convenience function
from extractor.core.convert import convert_pdf_to_json


def main():
    """Example usage of both approaches."""
    
    # Test PDF path
    pdf_path = "data/input/2505.03335v2.pdf"  # Update this
    
    if not Path(pdf_path).exists():
        print(f"Error: PDF not found at {pdf_path}")
        print("Please update the pdf_path variable with a valid PDF file path")
        return
    
    print("Method 1: Using convert_pdf_to_json convenience function")
    print("-" * 50)
    
    try:
        # Method 1: Convenience function
        result1 = convert_pdf_to_json(pdf_path, max_pages=2)  # Limit to 2 pages for demo
        print(f"✓ Converted {len(result1.get('children', []))} pages")
        print(f"✓ Block types found: {set(child['block_type'] for child in result1.get('children', []))}")
        
        # Save sample
        with open("method1_output.json", "w") as f:
            json.dump(result1, f, indent=2)
        print("✓ Saved to method1_output.json")
        
    except Exception as e:
        print(f"✗ Method 1 failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\nMethod 2: Using direct PdfConverter class")
    print("-" * 50)
    
    try:
        # Method 2: Direct converter usage
        result2 = convert_pdf_direct(pdf_path)
        print(f"✓ Converted {len(result2.get('children', []))} pages")
        
        # Show structure
        if result2.get('children'):
            first_page = result2['children'][0]
            print(f"✓ First page has {len(first_page.get('children', []))} blocks")
            
        # Save sample
        with open("method2_output.json", "w") as f:
            json.dump(result2, f, indent=2)
        print("✓ Saved to method2_output.json")
        
    except Exception as e:
        print(f"✗ Method 2 failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()