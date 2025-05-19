#!/usr/bin/env python3
"""Directly examine code blocks in a PDF"""

import json
import os
from pathlib import Path
import sys

# Add marker to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Direct imports of what we need
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.schema import BlockTypes

# PDF to test
pdf_path = "data/input/python-type-checking-readthedocs-io-en-latest.pdf"

if not os.path.exists(pdf_path):
    print(f"Error: PDF not found at {pdf_path}")
    exit(1)

print(f"Loading {pdf_path}...")

# Create minimal converter with only necessary processors
converter = PdfConverter(
    processor_list=[
        "marker.builders.document",
        "marker.builders.layout",
        "marker.builders.ocr", 
        "marker.processors.code",
        "marker.processors.text",
    ],
    artifact_dict=create_model_dict(),
    config={
        "disable_tqdm": True,
        "languages": ["English"],
        "disable_image_extraction": True,
        "page_range": "0-5",  # First 5 pages
    }
)

# Convert
try:
    document = converter(pdf_path)
    print(f"Document converted successfully with {len(document.pages)} pages")
except Exception as e:
    print(f"Error during conversion: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Find and examine code blocks
code_blocks = []

for page_idx, page in enumerate(document.pages):
    print(f"\nChecking page {page_idx + 1}...")
    
    # Look for code blocks
    for block_idx, block in enumerate(page.blocks):
        if block.block_type == BlockTypes.Code:
            # Get the actual text from the block
            try:
                code_text = block.code if hasattr(block, 'code') else block.raw_text(document)
                language = block.language if hasattr(block, 'language') else None
                
                code_info = {
                    "page": page_idx + 1,
                    "block_index": block_idx,
                    "language": language,
                    "code": code_text[:500],  # First 500 chars
                    "full_length": len(code_text)
                }
                code_blocks.append(code_info)
                
                print(f"  Found code block {block_idx}:")
                print(f"    Language: {language}")
                print(f"    Length: {len(code_text)} chars")
                print(f"    Preview: {repr(code_text[:100])}")
                
            except Exception as e:
                print(f"  Error processing block {block_idx}: {e}")

print(f"\nTotal code blocks found: {len(code_blocks)}")

# Save results
output_dir = "test_results/code_blocks"
os.makedirs(output_dir, exist_ok=True)

output_file = os.path.join(output_dir, "python_type_checking_code_blocks.json")
with open(output_file, "w") as f:
    json.dump(code_blocks, f, indent=2)

# Language summary
language_counts = {}
for block in code_blocks:
    lang = block["language"] or "undetected"
    language_counts[lang] = language_counts.get(lang, 0) + 1

print("\nCode blocks by language:")
for lang, count in sorted(language_counts.items()):
    print(f"  {lang}: {count}")

print(f"\nResults saved to {output_file}")

# Show detailed view of first Python code block
python_blocks = [b for b in code_blocks if b["language"] == "python"]
if python_blocks:
    print("\nFirst Python code block found:")
    first_python = python_blocks[0]
    print(f"Page: {first_python['page']}")
    print(f"Code:\n{first_python['code']}")