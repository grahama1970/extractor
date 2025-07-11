#!/usr/bin/env python3
"""
Module: simple_pdf_extract.py  
Description: Simplified PDF extraction using PyMuPDF for testing

External Dependencies:
- pymupdf: https://pymupdf.readthedocs.io/

Sample Input:
>>> pdf_path = "document.pdf"

Expected Output:
>>> text = extract_pdf_text(pdf_path)
>>> print(text[:100])
'Title of Document\n\nAbstract text...'

Example Usage:
>>> from extractor.simple_pdf_extract import extract_pdf_text
>>> text = extract_pdf_text("research_paper.pdf")
"""

import os
import sys
from pathlib import Path

def extract_pdf_text(pdf_path: str) -> str:
    """Extract text from PDF using PyMuPDF (fitz)"""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return f"Error: PyMuPDF not installed. Install with: pip install pymupdf"
    
    try:
        doc = fitz.open(pdf_path)
        text_parts = []
        
        for page_num, page in enumerate(doc):
            # Extract text from page
            text = page.get_text()
            if text.strip():
                text_parts.append(f"# Page {page_num + 1}\n\n{text}")
        
        doc.close()
        
        if text_parts:
            return "\n\n".join(text_parts)
        else:
            return "No text extracted from PDF (might be scanned/image PDF)"
            
    except Exception as e:
        return f"Error extracting PDF: {str(e)}"


def extract_pdf_with_structure(pdf_path: str) -> dict:
    """Extract PDF with structure information for unified JSON"""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return {"error": "PyMuPDF not installed"}
    
    try:
        doc = fitz.open(pdf_path)
        
        # Build document structure
        document = {
            "title": Path(pdf_path).stem,
            "metadata": {
                "page_count": len(doc),
                "source_file": pdf_path
            },
            "sections": [],
            "entities": [],
            "relationships": []
        }
        
        current_section_id = 0
        
        for page_num, page in enumerate(doc):
            # Get text blocks with position info
            blocks = page.get_text("dict")
            
            for block in blocks.get("blocks", []):
                if block.get("type") == 0:  # Text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span.get("text", "").strip()
                            if not text:
                                continue
                                
                            font_size = span.get("size", 12)
                            flags = span.get("flags", 0)
                            
                            # Detect headers by font size and bold
                            is_bold = flags & 2**4
                            is_header = font_size > 14 or is_bold
                            
                            if is_header and len(text) > 3:
                                # Create section
                                current_section_id += 1
                                section = {
                                    "id": f"section_{current_section_id}",
                                    "title": text,
                                    "level": 1 if font_size > 18 else 2,
                                    "content": "",
                                    "parent": None,
                                    "page": page_num + 1
                                }
                                document["sections"].append(section)
                            elif document["sections"]:
                                # Add to last section
                                document["sections"][-1]["content"] += f" {text}"
        
        doc.close()
        return document
        
    except Exception as e:
        return {"error": f"Error extracting PDF: {str(e)}"}


if __name__ == "__main__":
    # Test with real PDF files
    print("🧪 Testing Simple PDF Extraction")
    print("=" * 50)
    
    test_pdf = "/home/graham/workspace/experiments/extractor/data/input/2505.03335v2.pdf"
    
    # Test 1: Basic text extraction
    print("\n📝 Test 1: Basic Text Extraction")
    if os.path.exists(test_pdf):
        text = extract_pdf_text(test_pdf)
        print(f"✅ Extracted {len(text):,} characters")
        print(f"First 300 chars: {text[:300]}...")
        
        # Check for real content
        if "Error:" in text:
            print(f"❌ Extraction failed: {text}")
        elif len(text) < 100:
            print("❌ Extracted text too short - likely failed")
        else:
            print("✅ Successfully extracted text from PDF")
    else:
        print(f"⚠️  Test PDF not found: {test_pdf}")
    
    # Test 2: Structured extraction
    print("\n📝 Test 2: Structured Extraction")
    if os.path.exists(test_pdf):
        doc_struct = extract_pdf_with_structure(test_pdf)
        
        if "error" in doc_struct:
            print(f"❌ Structured extraction failed: {doc_struct['error']}")
        else:
            print(f"✅ Extracted structure:")
            print(f"   - Title: {doc_struct['title']}")
            print(f"   - Pages: {doc_struct['metadata']['page_count']}")
            print(f"   - Sections: {len(doc_struct['sections'])}")
            
            # Show first few sections
            for i, section in enumerate(doc_struct['sections'][:3]):
                print(f"   - Section {i+1}: {section['title'][:50]}...")
    
    print("\n" + "=" * 50)
    print("✅ Simple PDF extraction test complete")