#!/usr/bin/env python3
"""Simple test to check code detection in a PDF"""

import json
import os
from pathlib import Path

# Use marker's convert script directly
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import save_output

# PDF to test
pdf_path = "data/input/python-type-checking-readthedocs-io-en-latest.pdf"

if not os.path.exists(pdf_path):
    print(f"Error: PDF not found at {pdf_path}")
    exit(1)

print(f"Converting {pdf_path}...")

# Use default configuration with page range
processor_list = [
    "marker.builders.document",
    "marker.builders.layout", 
    "marker.builders.ocr",
    "marker.builders.structure",
    "marker.processors.line_merge",
    "marker.processors.code",  # This is the key processor for code detection
    "marker.processors.equation",
    "marker.processors.table",
    "marker.processors.text",
    "marker.processors.list",
    "marker.processors.section_header",
]

# Create converter
converter = PdfConverter(
    processor_list=processor_list,
    artifact_dict=create_model_dict(),
    config={
        "disable_tqdm": True,
        "page_range": "0-10",  # First 10 pages
    }
)

# Convert
document = converter(pdf_path)

print(f"Conversion complete. Document has {len(document.pages)} pages")

# Find all code blocks
code_blocks = []
for page_num, page in enumerate(document.pages):
    for block in page.blocks:
        if block.block_type == "Code":
            code_info = {
                "page": page_num,
                "language": getattr(block, 'language', None),
                "code": getattr(block, 'code', block.raw_text(document))[:500]  # First 500 chars
            }
            code_blocks.append(code_info)

print(f"\nFound {len(code_blocks)} code blocks")

# Show first few code blocks
for i, block in enumerate(code_blocks[:5]):
    print(f"\nCode Block {i+1}:")
    print(f"  Page: {block['page']}")
    print(f"  Language: {block['language']}")
    print(f"  Code (first 200 chars):")
    code_preview = block['code'][:200] + "..." if len(block['code']) > 200 else block['code']
    print(f"  {repr(code_preview)}")

# Save full results
output_dir = "test_results/code_detection"
os.makedirs(output_dir, exist_ok=True)

output_file = os.path.join(output_dir, "detected_code_blocks.json")
with open(output_file, "w") as f:
    json.dump(code_blocks, f, indent=2)

print(f"\nFull results saved to {output_file}")

# Language summary
language_counts = {}
for block in code_blocks:
    lang = block["language"] or "undetected"
    language_counts[lang] = language_counts.get(lang, 0) + 1

print("\nCode blocks by language:")
for lang, count in sorted(language_counts.items()):
    print(f"  {lang}: {count}")