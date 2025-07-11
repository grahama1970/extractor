#!/usr/bin/env python3
"""
Self-Contained PDF to JSON Extractor - Proof of Concept

This script extracts PDFs to structured JSON without any external dependencies
on the extractor module. It uses PyMuPDF (fitz) directly to parse PDFs and
creates a structured JSON output.

Requirements:
- PyMuPDF (pymupdf): pip install PyMuPDF

Usage:
- python self_contained_pdf_to_json.py [pdf_path]
"""

import json
import sys
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


def generate_id(text: str, prefix: str = "") -> str:
    """Generate a unique ID from text content."""
    hash_obj = hashlib.md5(text.encode('utf-8'))
    short_hash = hash_obj.hexdigest()[:8]
    return f"{prefix}_{short_hash}" if prefix else short_hash


def extract_pdf_to_json(pdf_path: str) -> Dict[str, Any]:
    """
    Extract PDF content to structured JSON using PyMuPDF.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dictionary with structured content including sections, text blocks, and metadata
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("Error: PyMuPDF not installed. Run: pip install PyMuPDF")
        return None
    
    # Open the PDF
    doc = fitz.open(pdf_path)
    doc_id = generate_id(pdf_path, "doc")
    
    # Initialize the result structure
    result = {
        "document": {
            "id": doc_id,
            "title": Path(pdf_path).stem,
            "source_file": str(Path(pdf_path).absolute()),
            "format": "pdf",
            "page_count": len(doc),
            "created_at": datetime.now().isoformat()
        },
        "pages": [],
        "sections": [],
        "text_blocks": [],
        "metadata": {
            "extractor": "PyMuPDF",
            "version": fitz.version,
            "extraction_time": None
        }
    }
    
    # Track extraction time
    start_time = datetime.now()
    
    # Extract content from each page
    all_text = ""
    section_id_counter = 0
    block_id_counter = 0
    current_section = None
    sections_hierarchy = []
    
    for page_num, page in enumerate(doc):
        page_dict = {
            "page_number": page_num + 1,
            "width": page.rect.width,
            "height": page.rect.height,
            "rotation": page.rotation,
            "blocks": []
        }
        
        # Get text blocks with formatting info
        blocks = page.get_text("dict")
        
        for block_idx, block in enumerate(blocks.get("blocks", [])):
            if block.get("type") == 0:  # Text block
                block_id_counter += 1
                block_text = ""
                block_info = {
                    "id": f"block_{block_id_counter}",
                    "page": page_num + 1,
                    "bbox": block.get("bbox", []),
                    "lines": []
                }
                
                for line in block.get("lines", []):
                    line_text = ""
                    line_info = {
                        "bbox": line.get("bbox", []),
                        "spans": []
                    }
                    
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue
                        
                        line_text += text + " "
                        font_size = span.get("size", 12)
                        font_name = span.get("font", "")
                        flags = span.get("flags", 0)
                        
                        # Detect formatting
                        is_bold = bool(flags & 2**4)
                        is_italic = bool(flags & 2**1)
                        
                        span_info = {
                            "text": text,
                            "font_size": font_size,
                            "font_name": font_name,
                            "is_bold": is_bold,
                            "is_italic": is_italic,
                            "bbox": span.get("bbox", [])
                        }
                        line_info["spans"].append(span_info)
                        
                        # Detect headers based on font size and formatting
                        is_header = False
                        header_level = 0
                        
                        if font_size > 20 or (is_bold and font_size > 16):
                            is_header = True
                            header_level = 1
                        elif font_size > 16 or (is_bold and font_size > 14):
                            is_header = True
                            header_level = 2
                        elif font_size > 14 or (is_bold and font_size > 12):
                            is_header = True
                            header_level = 3
                        elif is_bold and len(text) > 3:
                            is_header = True
                            header_level = 4
                        
                        # Create section for headers
                        if is_header and len(text) > 3:
                            # Save previous section if exists
                            if current_section and current_section.get("content"):
                                result["sections"].append(current_section)
                            
                            section_id_counter += 1
                            section_id = f"section_{section_id_counter}"
                            
                            # Determine parent section
                            parent_id = None
                            while sections_hierarchy and sections_hierarchy[-1][1] >= header_level:
                                sections_hierarchy.pop()
                            
                            if sections_hierarchy:
                                parent_id = sections_hierarchy[-1][0]
                            
                            current_section = {
                                "id": section_id,
                                "title": text,
                                "level": header_level,
                                "page": page_num + 1,
                                "parent_id": parent_id,
                                "content": "",
                                "bbox": span.get("bbox", [])
                            }
                            
                            sections_hierarchy.append((section_id, header_level))
                    
                    if line_text.strip():
                        block_text += line_text.strip() + "\n"
                        block_info["lines"].append(line_info)
                
                # Add content to current section or create default section
                if block_text.strip():
                    if current_section:
                        if current_section["content"]:
                            current_section["content"] += "\n"
                        current_section["content"] += block_text.strip()
                    else:
                        # Create a default section for content before first header
                        section_id_counter += 1
                        current_section = {
                            "id": f"section_{section_id_counter}",
                            "title": "Document Start",
                            "level": 1,
                            "page": page_num + 1,
                            "parent_id": None,
                            "content": block_text.strip(),
                            "bbox": block.get("bbox", [])
                        }
                    
                    block_info["text"] = block_text.strip()
                    result["text_blocks"].append(block_info)
                    page_dict["blocks"].append(block_info["id"])
                    all_text += block_text + "\n"
        
        result["pages"].append(page_dict)
    
    # Don't forget the last section
    if current_section and current_section.get("content"):
        result["sections"].append(current_section)
    
    # Close the document
    doc.close()
    
    # Calculate extraction time
    extraction_time = (datetime.now() - start_time).total_seconds()
    result["metadata"]["extraction_time"] = f"{extraction_time:.2f} seconds"
    
    # Add summary statistics
    result["summary"] = {
        "total_pages": len(result["pages"]),
        "total_sections": len(result["sections"]),
        "total_text_blocks": len(result["text_blocks"]),
        "total_characters": len(all_text),
        "extraction_successful": True
    }
    
    return result


def main():
    """Main function to run the PDF extraction."""
    # Check command line arguments
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Default test PDF
        pdf_path = "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2.pdf"
        if not Path(pdf_path).exists():
            print("Usage: python self_contained_pdf_to_json.py <pdf_path>")
            print(f"\nDefault test PDF not found: {pdf_path}")
            return 1
    
    # Check if PDF exists
    if not Path(pdf_path).exists():
        print(f"Error: PDF file not found: {pdf_path}")
        return 1
    
    print(f"📄 Extracting PDF: {pdf_path}")
    print("⏳ Processing...")
    
    # Extract PDF
    result = extract_pdf_to_json(pdf_path)
    
    if result:
        # Save to JSON file
        output_path = Path(__file__).parent / f"{Path(pdf_path).stem}_extracted.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        # Print summary
        print(f"\n✅ Extraction complete!")
        print(f"\n📊 Summary:")
        print(f"   - Pages: {result['summary']['total_pages']}")
        print(f"   - Sections: {result['summary']['total_sections']}")
        print(f"   - Text blocks: {result['summary']['total_text_blocks']}")
        print(f"   - Total characters: {result['summary']['total_characters']:,}")
        print(f"   - Extraction time: {result['metadata']['extraction_time']}")
        
        # Show sample sections
        if result['sections']:
            print(f"\n📑 Sample sections:")
            for i, section in enumerate(result['sections'][:10]):
                indent = "  " * (section['level'] - 1)
                print(f"   {indent}[L{section['level']}] {section['title']}")
        
        print(f"\n💾 Output saved to: {output_path}")
        print(f"   File size: {output_path.stat().st_size / 1024:.1f} KB")
        
        return 0
    else:
        print("❌ Extraction failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())