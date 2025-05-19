#!/usr/bin/env python3
"""Test code detection by converting a PDF and examining code blocks"""

import sys
import os
import json
from pathlib import Path

# Add marker to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser
from marker.cli.search import DocumentSearchEngine

# PDF to test
pdf_path = "data/input/python-type-checking-readthedocs-io-en-latest.pdf"

if not os.path.exists(pdf_path):
    print(f"Error: PDF not found at {pdf_path}")
    sys.exit(1)

# Configure converter
config = {
    "disable_tqdm": True,
    "debug": False,
    "page_range": "0-10",  # First 10 pages for speed
}

# Create converter
config_parser = ConfigParser(config)
converter = PdfConverter(
    config=config_parser.generate_config_dict(),
    artifact_dict=create_model_dict(),
    processor_list=config_parser.get_processors(),
    renderer=config_parser.get_renderer()
)

print(f"Converting {pdf_path}...")
document = converter(pdf_path)

# Save the document for inspection
output_dir = "test_results/code_detection"
os.makedirs(output_dir, exist_ok=True)

# Search for code blocks
search_engine = DocumentSearchEngine(document)

print("\n=== Searching for Code Blocks ===")
results = search_engine.search("code", section_types=["Code"])

if results:
    print(f"Found {len(results)} code blocks\n")
    
    # Show first few code blocks to verify language detection
    for i, result in enumerate(results[:5]):
        print(f"Code Block {i+1}:")
        print(f"  Page: {result['page']}")
        print(f"  Section Type: {result['section_type']}")
        if hasattr(result['block'], 'language'):
            print(f"  Detected Language: {result['block'].language}")
        print(f"  Code snippet (first 100 chars):")
        code_text = result['text'][:100] + "..." if len(result['text']) > 100 else result['text']
        print(f"  {repr(code_text)}")
        print()
else:
    print("No code blocks found")

# Also save document structure for inspection
doc_structure = {
    "pages": len(document.pages),
    "code_blocks": []
}

# Extract all code blocks
for page_num, page in enumerate(document.pages):
    for block in page.contained_blocks(document, ["Code"]):
        code_info = {
            "page": page_num,
            "language": getattr(block, 'language', None),
            "code_preview": block.code[:200] if hasattr(block, 'code') else block.raw_text(document)[:200]
        }
        doc_structure["code_blocks"].append(code_info)

# Save structure
with open(os.path.join(output_dir, "code_blocks.json"), "w") as f:
    json.dump(doc_structure, f, indent=2)

print(f"\nDocument structure saved to {output_dir}/code_blocks.json")
print(f"Total code blocks found: {len(doc_structure['code_blocks'])}")

# Group by language
language_counts = {}
for block in doc_structure["code_blocks"]:
    lang = block["language"] or "undetected"
    language_counts[lang] = language_counts.get(lang, 0) + 1

print("\nCode blocks by language:")
for lang, count in sorted(language_counts.items()):
    print(f"  {lang}: {count}")