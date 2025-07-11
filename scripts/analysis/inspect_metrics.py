"""
Module: inspect_metrics.py

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

#!/usr/bin/env python3
"""
Script to inspect the actual structure and metrics of a PDF document.
"""

import json
from pathlib import Path
from marker.models import create_model_dict
from marker.config.parser import ConfigParser
from marker.logger import configure_logging

def inspect_document_structure(filepath: str):
    """Inspect the structure of a PDF document."""
    configure_logging()
    
    # Create models and config
    models = create_model_dict()
    config_dict = {"output_format": "json"}
    config_parser = ConfigParser(config_dict)
    
    # Get converter class and create converter
    converter_cls = config_parser.get_converter_cls()
    converter = converter_cls(
        config=config_parser.generate_config_dict(),
        artifact_dict=models,
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service()
    )
    
    # Convert the PDF
    print(f"Converting {filepath}...")
    rendered = converter(filepath)
    
    print("\n=== Document Structure ===")
    print(f"Type: {type(rendered)}")
    print(f"Attributes: {dir(rendered)}")
    
    # Check metadata
    if hasattr(rendered, "metadata"):
        print("\n=== Metadata ===")
        print(json.dumps(rendered.metadata, indent=2))
    
    # Count block types
    if hasattr(rendered, "children"):
        print(f"\n=== Top-level children: {len(rendered.children)} ===")
        
        def count_blocks(blocks, level=0):
            counts = {}
            for block in blocks:
                block_type = getattr(block, "block_type", "unknown")
                counts[block_type] = counts.get(block_type, 0) + 1
                
                # Print structure
                print(f"{'  ' * level}{block_type} - {getattr(block, 'id', 'no-id')}")
                
                # Recurse through children
                if hasattr(block, "children") and block.children:
                    print(f"{'  ' * level}  -> {len(block.children)} children")
                    child_counts = count_blocks(block.children, level + 1)
                    # Merge child counts
                    for k, v in child_counts.items():
                        counts[k] = counts.get(k, 0) + v
            
            return counts
        
        all_counts = count_blocks(rendered.children)
        
        print("\n=== Block Type Counts ===")
        for block_type, count in sorted(all_counts.items()):
            print(f"{block_type}: {count}")
    
    # Sample a page if available
    if hasattr(rendered, "children") and rendered.children:
        first_page = rendered.children[0]
        print(f"\n=== First Page Structure ===")
        print(f"Type: {getattr(first_page, 'block_type', 'unknown')}")
        if hasattr(first_page, "children"):
            print(f"Children: {len(first_page.children)}")
            for i, child in enumerate(first_page.children[:5]):
                print(f"  Child {i}: {getattr(child, 'block_type', 'unknown')}")
                if hasattr(child, "children") and child.children:
                    print(f"    -> {len(child.children)} nested children")


if __name__ == "__main__":
    test_pdf = "./repos/camelot/docs/_static/pdf/copy_text.pdf"
    inspect_document_structure(test_pdf)