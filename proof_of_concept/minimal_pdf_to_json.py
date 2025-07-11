#!/usr/bin/env python3
"""
Minimal PDF to JSON Extractor

The bare minimum code to extract PDF content to structured JSON.
"""

import json
import fitz  # PyMuPDF

def extract_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    
    result = {
        "pages": [],
        "sections": []
    }
    
    for page_num, page in enumerate(doc):
        # Get text blocks
        blocks = page.get_text("dict")
        
        for block in blocks["blocks"]:
            if block["type"] == 0:  # Text block
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        if text:
                            # Check if header (bold or large font)
                            is_header = span["size"] > 14 or (span["flags"] & 2**4)
                            
                            if is_header:
                                result["sections"].append({
                                    "title": text,
                                    "page": page_num + 1
                                })
    
    doc.close()
    return result

# Usage
if __name__ == "__main__":
    import sys
    
    # Use provided PDF or default test PDF
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2.pdf"
    
    data = extract_pdf(pdf_path)
    
    output_file = "minimal_output.json"
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"Extracted {len(data['sections'])} sections")
    print(f"Saved to {output_file}")