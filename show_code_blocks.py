#!/usr/bin/env python3
"""
Show code blocks from a PDF using Marker
"""

import os
import sys
import time
from pathlib import Path
import json

# Ensure we're running from the project root
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# Import marker modules
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.schema import BlockTypes
from marker.schema.document import Document

def extract_code_blocks(document: Document) -> list:
    """Extract all code blocks from the document"""
    code_blocks = []
    
    # Get all code blocks
    blocks = document.contained_blocks((BlockTypes.Code,))
    
    for i, block in enumerate(blocks):
        # Get code text
        code_text = block.code if hasattr(block, 'code') else block.raw_text(document)
        
        # Get language if available
        language = block.language if hasattr(block, 'language') else None
        
        # Find which page this block is on
        page_num = None
        for page_idx, page in enumerate(document.pages):
            if block in page.blocks:
                page_num = page_idx
                break
        
        code_info = {
            "index": i,
            "page": page_num,
            "language": language,
            "code": code_text,
            "block_id": str(block.id),
            "metadata": getattr(block, 'metadata', None)
        }
        code_blocks.append(code_info)
    
    return code_blocks

def main():
    # PDF to analyze
    pdf_path = "data/input/python-type-checking-readthedocs-io-en-latest.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"Error: PDF not found at {pdf_path}")
        return 1
    
    # Create configuration for first 10 pages
    config = {
        "page_range": range(0, 10),  # 0-indexed pages
        "disable_tqdm": True,
    }
    
    print(f"Loading PDF: {pdf_path}")
    print("Pages: 0-9 (first 10 pages)")
    
    # Initialize converter
    converter = PdfConverter(
        artifact_dict=create_model_dict(),
        config=config
    )
    
    # Load document
    start_time = time.time()
    document = converter.build_document(pdf_path)
    load_time = time.time() - start_time
    
    print(f"Document loaded in {load_time:.2f} seconds")
    print(f"Total pages: {len(document.pages)}")
    
    # Extract code blocks
    code_blocks = extract_code_blocks(document)
    
    print(f"\n=== Found {len(code_blocks)} Code Blocks ===\n")
    
    # Show first few code blocks
    for block in code_blocks[:5]:  # Show first 5
        print(f"Code Block {block['index'] + 1}:")
        print(f"  Page: {block['page']}")
        print(f"  Language: {block['language']}")
        print(f"  Code length: {len(block['code'])} chars")
        print(f"  Code preview:")
        # Show first 200 characters
        preview = block['code'][:200] + "..." if len(block['code']) > 200 else block['code']
        print(f"  {repr(preview)}")
        print()
    
    # Language summary
    language_counts = {}
    for block in code_blocks:
        lang = block['language'] or 'undetected'
        language_counts[lang] = language_counts.get(lang, 0) + 1
    
    print("\n=== Language Summary ===")
    for lang, count in sorted(language_counts.items()):
        print(f"  {lang}: {count}")
    
    # Save all results
    output_dir = "test_results/code_blocks"
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, "type_checking_code_blocks.json")
    with open(output_file, "w") as f:
        json.dump(code_blocks, f, indent=2)
    
    print(f"\nFull results saved to: {output_file}")
    
    # Show one Python example with full code
    python_blocks = [b for b in code_blocks if b['language'] == 'python']
    if python_blocks:
        print("\n=== Example Python Code Block ===")
        example = python_blocks[0]
        print(f"Page: {example['page']}")
        print(f"Full code:")
        print(example['code'])
    
    return 0

if __name__ == "__main__":
    sys.exit(main())