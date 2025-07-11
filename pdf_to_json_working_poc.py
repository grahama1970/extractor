#!/usr/bin/env python3
"""
Working proof of concept for PDF to JSON conversion.

This shows the correct way to use the extractor module to convert PDFs to structured JSON.
Based on the working examples in the codebase.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional

# Setup environment
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def extract_pdf_using_unified_extractor(pdf_path: str) -> Dict[str, Any]:
    """
    Extract PDF using the unified extractor (recommended approach).
    
    This uses the higher-level unified extractor that handles:
    - Proper Surya model integration
    - Bold header parsing
    - Structured JSON output for ArangoDB
    """
    try:
        # Import the unified extractor (v2 or v3)
        from extractor.unified_extractor_v2 import extract_to_unified_json
        
        print(f"Extracting PDF using unified extractor: {pdf_path}")
        result = extract_to_unified_json(pdf_path)
        
        # The result is already a proper dict structure
        return result
        
    except ImportError:
        print("Trying v3...")
        from extractor.unified_extractor_v3 import extract_to_unified_json
        return extract_to_unified_json(pdf_path)


def extract_pdf_using_core_converter(pdf_path: str) -> Dict[str, Any]:
    """
    Extract PDF using the core converter directly.
    
    This is the lower-level approach that gives more control.
    """
    from extractor.core.converters.pdf import convert_single_pdf
    
    print(f"Extracting PDF using core converter: {pdf_path}")
    
    # Convert to markdown first (original marker behavior)
    markdown_result = convert_single_pdf(
        pdf_path,
        max_pages=None,  # Process all pages
        langs=["English"],
        ocr_all_pages=False
    )
    
    # Handle both string and object returns
    if isinstance(markdown_result, str):
        markdown_content = markdown_result
    else:
        markdown_content = markdown_result.markdown if hasattr(markdown_result, 'markdown') else str(markdown_result)
    
    # Create a structured JSON response
    result = {
        "format": "markdown",
        "content": markdown_content,
        "metadata": {
            "source": pdf_path,
            "extractor": "core.converters.pdf"
        }
    }
    
    return result


def extract_pdf_using_json_renderer(pdf_path: str) -> Dict[str, Any]:
    """
    Extract PDF directly to JSON using the JSON renderer.
    
    This approach uses the PdfConverter with JSONRenderer.
    """
    from extractor.core.converters.pdf import PdfConverter
    from extractor.core.renderers.json import JSONRenderer
    from extractor.core.models import create_model_dict
    
    print(f"Extracting PDF using JSON renderer: {pdf_path}")
    
    # Create model dictionary
    models = create_model_dict()
    
    # Configure converter
    config = {
        "disable_multiprocessing": True,
        "disable_tqdm": True,
        "use_llm": False,
    }
    
    # Create converter with JSON renderer
    converter = PdfConverter(
        artifact_dict=models,
        renderer="extractor.core.renderers.json.JSONRenderer",
        config=config
    )
    
    # Convert PDF
    json_output = converter(pdf_path)
    
    # The output is a pydantic model, convert to dict carefully
    # Based on the error, we need to handle this differently
    try:
        # Try the standard model_dump
        return json_output.model_dump()
    except Exception:
        # Fallback: manually convert
        result = {
            "children": [],
            "block_type": "Document",
            "metadata": {}
        }
        
        # Extract data from the pydantic model
        if hasattr(json_output, 'children'):
            for child in json_output.children:
                child_dict = {
                    "id": str(child.id) if hasattr(child, 'id') else "",
                    "block_type": str(child.block_type) if hasattr(child, 'block_type') else "",
                    "html": child.html if hasattr(child, 'html') else "",
                    "bbox": child.bbox if hasattr(child, 'bbox') else [],
                    "polygon": child.polygon if hasattr(child, 'polygon') else [],
                }
                result["children"].append(child_dict)
        
        if hasattr(json_output, 'metadata'):
            result["metadata"] = dict(json_output.metadata) if isinstance(json_output.metadata, dict) else {}
        
        return result


def main():
    """Main function demonstrating different extraction approaches."""
    
    # Test PDF path
    test_pdf = "data/input/2505.03335v2.pdf"
    
    if len(sys.argv) > 1:
        test_pdf = sys.argv[1]
    
    if not Path(test_pdf).exists():
        print(f"Error: PDF not found: {test_pdf}")
        print("\nUsage: python pdf_to_json_working_poc.py [pdf_path]")
        return
    
    print("PDF TO JSON EXTRACTION - WORKING METHODS")
    print("=" * 60)
    
    # Method 1: Unified Extractor (Recommended)
    print("\n1. UNIFIED EXTRACTOR METHOD (Recommended)")
    print("-" * 40)
    try:
        result1 = extract_pdf_using_unified_extractor(test_pdf)
        
        sections = result1.get('vertices', {}).get('sections', [])
        print(f"✓ Extracted {len(sections)} sections")
        print(f"✓ Structure: vertices & edges format (ArangoDB compatible)")
        
        # Save output
        with open("method1_unified_output.json", "w") as f:
            json.dump(result1, f, indent=2)
        print("✓ Saved to: method1_unified_output.json")
        
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Method 2: Core Converter (Markdown)
    print("\n2. CORE CONVERTER METHOD (Markdown)")
    print("-" * 40)
    try:
        result2 = extract_pdf_using_core_converter(test_pdf)
        
        content_length = len(result2.get('content', ''))
        print(f"✓ Extracted {content_length:,} characters of markdown")
        
        # Save output
        with open("method2_markdown_output.json", "w") as f:
            json.dump(result2, f, indent=2)
        print("✓ Saved to: method2_markdown_output.json")
        
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Method 3: JSON Renderer (Direct)
    print("\n3. JSON RENDERER METHOD (Direct)")
    print("-" * 40)
    try:
        result3 = extract_pdf_using_json_renderer(test_pdf)
        
        pages = result3.get('children', [])
        print(f"✓ Extracted {len(pages)} pages")
        
        # Count blocks
        total_blocks = sum(len(page.get('children', [])) for page in pages)
        print(f"✓ Total blocks: {total_blocks}")
        
        # Save output
        with open("method3_json_output.json", "w") as f:
            json.dump(result3, f, indent=2)
        print("✓ Saved to: method3_json_output.json")
        
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("- Method 1 (Unified): Best for structured extraction with sections")
    print("- Method 2 (Core): Best for markdown output")
    print("- Method 3 (JSON): Best for raw block-level data")
    print("\nCheck the output files to see the different formats!")


def working_usage():
    """Simple working example for copy-paste."""
    # This is the simplest working approach
    from extractor.unified_extractor_v2 import extract_to_unified_json
    
    pdf_path = "data/input/2505.03335v2.pdf"
    result = extract_to_unified_json(pdf_path)
    
    print(f"Extracted {len(result['vertices']['sections'])} sections")
    
    with open("output.json", "w") as f:
        json.dump(result, f, indent=2)


def debug_function():
    """Debug function for testing."""
    main()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].endswith('.pdf') else "working"
    
    if mode == "debug" or (len(sys.argv) > 1 and sys.argv[1].endswith('.pdf')):
        debug_function()
    else:
        working_usage()