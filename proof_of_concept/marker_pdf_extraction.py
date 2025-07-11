#!/usr/bin/env python3
"""
Marker-PDF to JSON Extraction - Proof of Concept

This demonstrates using the marker-pdf functionality from the extractor module
to convert PDFs to structured JSON, without using the unified_extractor wrapper.

Uses the core marker-pdf conversion pipeline directly.
"""

import os
import sys
import json
from pathlib import Path

# Environment setup for marker-pdf
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

# Add extractor source to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import the core marker-pdf functionality
from extractor.core.converters.pdf import convert_single_pdf
from extractor.core.converters.pdf import PdfConverter
from extractor.core.renderers.json import JSONRenderer
from extractor.core.models import create_model_dict


def extract_pdf_using_marker(pdf_path: str) -> dict:
    """
    Extract PDF to JSON using marker-pdf's convert_single_pdf function.
    
    This uses the marker-pdf converter to get markdown, then parses it.
    """
    print(f"Extracting with marker-pdf: {pdf_path}")
    
    # Use marker-pdf to convert to markdown
    markdown_result = convert_single_pdf(
        pdf_path,
        max_pages=None,  # Process all pages
        langs=["English"],
        ocr_all_pages=False
    )
    
    # Handle both string and object returns
    if isinstance(markdown_result, str):
        markdown_text = markdown_result
    else:
        markdown_text = getattr(markdown_result, 'markdown', str(markdown_result))
    
    # Parse markdown to extract structure
    sections = []
    lines = markdown_text.split('\n')
    current_section = None
    section_id = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Detect markdown headers
        if line.startswith('#'):
            # Count header level
            level = len(line) - len(line.lstrip('#'))
            title = line[level:].strip()
            
            if title:
                # Save previous section
                if current_section and current_section.get('content'):
                    sections.append(current_section)
                
                # Create new section
                section_id += 1
                current_section = {
                    "id": f"section_{section_id}",
                    "title": title,
                    "level": level,
                    "content": ""
                }
        elif current_section:
            # Add content to current section
            if current_section['content']:
                current_section['content'] += '\n'
            current_section['content'] += line
        else:
            # Content before first header
            if not sections and not current_section:
                section_id += 1
                current_section = {
                    "id": f"section_{section_id}", 
                    "title": "Introduction",
                    "level": 1,
                    "content": line
                }
    
    # Don't forget the last section
    if current_section and current_section.get('content'):
        sections.append(current_section)
    
    return {
        "document": {
            "source": pdf_path,
            "extractor": "marker-pdf (convert_single_pdf)"
        },
        "sections": sections,
        "markdown_length": len(markdown_text)
    }


def extract_pdf_using_json_renderer(pdf_path: str) -> dict:
    """
    Extract PDF directly to JSON using marker-pdf's PdfConverter with JSONRenderer.
    
    This approach uses the full marker-pdf pipeline with JSON output.
    """
    print(f"Extracting with marker-pdf JSONRenderer: {pdf_path}")
    
    # Create model dictionary for marker-pdf
    models = create_model_dict()
    
    # Configure the converter
    config = {
        "disable_multiprocessing": True,
        "disable_tqdm": True,
        "use_llm": False,  # Disable LLM for speed
    }
    
    # Create PdfConverter with JSON renderer
    converter = PdfConverter(
        artifact_dict=models,
        renderer="extractor.core.renderers.json.JSONRenderer",
        config=config
    )
    
    # Convert PDF to JSON
    json_output = converter(pdf_path)
    
    # The output is a pydantic model, extract the data
    if hasattr(json_output, 'model_dump'):
        try:
            return json_output.model_dump()
        except:
            pass
    
    # Manual extraction if model_dump fails
    result = {
        "children": [],
        "metadata": {}
    }
    
    if hasattr(json_output, 'children'):
        for child in json_output.children:
            child_data = {
                "id": str(getattr(child, 'id', '')),
                "block_type": str(getattr(child, 'block_type', '')),
                "html": getattr(child, 'html', ''),
                "bbox": getattr(child, 'bbox', []),
                "children": []
            }
            
            if hasattr(child, 'children') and child.children:
                for subchild in child.children:
                    subchild_data = {
                        "html": getattr(subchild, 'html', ''),
                        "block_type": str(getattr(subchild, 'block_type', ''))
                    }
                    child_data["children"].append(subchild_data)
            
            result["children"].append(child_data)
    
    if hasattr(json_output, 'metadata'):
        result["metadata"] = dict(json_output.metadata) if hasattr(json_output.metadata, '__dict__') else {}
    
    return result


def main():
    """Main function demonstrating both extraction methods."""
    
    # Get PDF path
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = str(Path(__file__).parent / "2505.03335v2.pdf")
    
    if not Path(pdf_path).exists():
        print(f"Error: PDF not found: {pdf_path}")
        return 1
    
    print("=" * 60)
    print("MARKER-PDF EXTRACTION DEMO")
    print("=" * 60)
    
    # Method 1: Using convert_single_pdf (markdown intermediate)
    print("\n1. Using convert_single_pdf (Markdown):")
    print("-" * 40)
    
    try:
        result1 = extract_pdf_using_marker(pdf_path)
        
        output1 = Path(__file__).parent / "marker_markdown_output.json"
        with open(output1, 'w', encoding='utf-8') as f:
            json.dump(result1, f, indent=2)
        
        print(f"✓ Extracted {len(result1['sections'])} sections")
        print(f"✓ Markdown length: {result1['markdown_length']:,} chars")
        print(f"✓ Saved to: {output1}")
        
        # Show sample sections
        print("\nSample sections:")
        for section in result1['sections'][:5]:
            print(f"  [{section['level']}] {section['title'][:50]}...")
            
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Method 2: Using PdfConverter with JSONRenderer
    print("\n\n2. Using PdfConverter with JSONRenderer:")
    print("-" * 40)
    
    try:
        result2 = extract_pdf_using_json_renderer(pdf_path)
        
        output2 = Path(__file__).parent / "marker_json_output.json"
        with open(output2, 'w', encoding='utf-8') as f:
            json.dump(result2, f, indent=2)
        
        pages = result2.get('children', [])
        total_blocks = sum(len(page.get('children', [])) for page in pages)
        
        print(f"✓ Extracted {len(pages)} pages")
        print(f"✓ Total blocks: {total_blocks}")
        print(f"✓ Saved to: {output2}")
        
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("Both methods use marker-pdf core functionality:")
    print("- Method 1: Simpler, produces sections from markdown")
    print("- Method 2: Full pipeline, produces detailed block structure")


if __name__ == "__main__":
    main()