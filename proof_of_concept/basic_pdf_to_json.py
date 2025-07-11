#!/usr/bin/env python3
"""
Basic PDF to JSON Extractor - Clean and Simple

Extracts PDF content with proper section detection.
Only requires PyMuPDF: pip install PyMuPDF
"""

import json
import sys
import fitz  # PyMuPDF

def extract_pdf_to_json(pdf_path):
    """Extract PDF to structured JSON with sections and content."""
    doc = fitz.open(pdf_path)
    
    sections = []
    current_section = None
    
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")
        
        for block in blocks["blocks"]:
            if block["type"] == 0:  # Text block
                block_text = ""
                
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        if not text:
                            continue
                        
                        # Detect headers: large font OR bold text
                        font_size = span["size"]
                        is_bold = span["flags"] & 2**4  # Bold flag
                        
                        # Header if: size > 14 OR (bold AND size > 12 AND length > 3)
                        is_header = (font_size > 14) or (is_bold and font_size > 12 and len(text) > 3)
                        
                        if is_header and not text.startswith("!["):  # Skip image refs
                            # Save previous section
                            if current_section and current_section.get("content"):
                                sections.append(current_section)
                            
                            # Start new section
                            current_section = {
                                "title": text,
                                "page": page_num + 1,
                                "content": ""
                            }
                        elif current_section:
                            # Add to current section content
                            block_text += text + " "
                
                # Add block text to current section
                if current_section and block_text.strip():
                    if current_section["content"]:
                        current_section["content"] += "\n"
                    current_section["content"] += block_text.strip()
    
    # Don't forget the last section
    if current_section and current_section.get("content"):
        sections.append(current_section)
    
    # Get page count before closing
    page_count = doc.page_count
    doc.close()
    
    return {
        "document": {
            "source": pdf_path,
            "pages": page_count
        },
        "sections": sections
    }

if __name__ == "__main__":
    # Get PDF path from command line or use default
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "/home/graham/workspace/experiments/extractor/proof_of_concept/2505.03335v2.pdf"
    
    # Extract
    result = extract_pdf_to_json(pdf_path)
    
    # Save
    with open("basic_output.json", "w") as f:
        json.dump(result, f, indent=2)
    
    # Summary
    print(f"✓ Extracted {len(result['sections'])} sections from {result['document']['pages']} pages")
    print("✓ Saved to basic_output.json")
    
    # Show first 5 sections
    print("\nFirst 5 sections:")
    for i, section in enumerate(result['sections'][:5]):
        print(f"{i+1}. {section['title'][:60]}...")