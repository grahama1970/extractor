#!/usr/bin/env python3
"""
Marker-PDF Direct JSON Access - Proof of Concept

Shows how to get the JSON structure directly from marker's document object.
"""

import json
from pathlib import Path
import sys

# Import from the ACTUAL marker package structure
from marker.convert import convert_single_pdf
from marker.models import load_all_models


def get_marker_json(pdf_path: str):
    """
    Get JSON structure directly from marker's conversion.
    
    Returns the document structure as JSON with pages, blocks, etc.
    """
    print("Loading marker models...")
    model_lst = load_all_models()
    
    print(f"Converting PDF: {pdf_path}")
    
    # Convert PDF - this returns markdown text, images dict, and metadata
    full_text, images, out_meta = convert_single_pdf(
        pdf_path,
        model_lst,
        max_pages=None,
        langs=None,
        batch_multiplier=2
    )
    
    # The out_meta contains the document structure
    # Check if it has pages attribute or if it's already a dict
    if hasattr(out_meta, 'pages'):
        # It's a Document object, convert to dict
        pages = []
        for page in out_meta.pages:
            page_dict = {
                "id": page.id,
                "block_type": page.block_type,
                "html": page.html,
                "polygon": page.polygon,
                "children": []
            }
            
            # Add children blocks
            if hasattr(page, 'children') and page.children:
                for child in page.children:
                    child_dict = {
                        "id": child.id,
                        "block_type": child.block_type,
                        "html": child.html,
                        "polygon": child.polygon,
                        "section_hierarchy": getattr(child, 'section_hierarchy', {}),
                        "images": {}
                    }
                    page_dict["children"].append(child_dict)
            
            pages.append(page_dict)
        
        return pages, images
    else:
        # It might already be in the right format
        return out_meta, images


def main():
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "2505.03335v2.pdf"
    
    if not Path(pdf_path).exists():
        print(f"Error: PDF not found: {pdf_path}")
        return 1
    
    # Get the JSON structure
    document_json, images = get_marker_json(pdf_path)
    
    # Save to file
    output_path = Path(pdf_path).stem + "_marker_output.json"
    
    output_data = {
        "document": document_json,
        "images": {k: v for k, v in images.items()}  # Convert images dict
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"✓ Saved JSON to: {output_path}")
    
    # Show structure
    if isinstance(document_json, list):
        print(f"✓ Extracted {len(document_json)} pages")
        if document_json:
            first_page = document_json[0]
            print(f"✓ First page has {len(first_page.get('children', []))} blocks")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())