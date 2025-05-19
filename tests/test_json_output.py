#!/usr/bin/env python3
"""
Test script to compare regular JSON vs merged JSON output.
"""

import json
from pathlib import Path
from typing import Dict
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.util import strings_to_classes


def count_blocks(data: Dict, block_counts: Dict = None) -> Dict:
    """Count block types recursively."""
    if block_counts is None:
        block_counts = {}
    
    if isinstance(data, dict):
        if "block_type" in data:
            block_type = data["block_type"]
            block_counts[block_type] = block_counts.get(block_type, 0) + 1
        
        if "children" in data and data["children"]:
            for child in data["children"]:
                count_blocks(child, block_counts)
                
        # Also count pages if present
        if "pages" in data and isinstance(data["pages"], list):
            for page in data["pages"]:
                count_blocks(page, block_counts)
    
    return block_counts


def main():
    # Test with a PDF file that likely has more text blocks
    pdf_path = "./repos/camelot/docs/benchmark/stream/health/health.pdf"
    
    # Create model dict
    models = create_model_dict()
    
    # Create converter with regular JSON renderer
    converter = PdfConverter(
        config={},
        artifact_dict=models,
        processor_list=None,
        renderer="marker.renderers.json.JSONRenderer"
    )
    
    # Convert PDF to JSON
    rendered = converter(str(pdf_path))
    
    # Get JSON string from the rendered output
    if hasattr(rendered, "model_dump_json"):
        regular_json = rendered.model_dump_json(exclude=["metadata"], indent=2)
    else:
        # If it's already a string, use it directly
        regular_json = str(rendered)
    
    # Parse JSON string to dict for counting
    regular_data = json.loads(regular_json)
    regular_counts = count_blocks(regular_data)
    
    # Now create converter with merged JSON renderer
    converter_merged = PdfConverter(
        config={},
        artifact_dict=models,
        processor_list=None,
        renderer="marker.renderers.merged_json.MergedJSONRenderer"
    )
    
    # Convert PDF to merged JSON
    rendered_merged = converter_merged(str(pdf_path))
    
    # Get JSON string from the rendered output
    if hasattr(rendered_merged, "model_dump_json"):
        merged_json = rendered_merged.model_dump_json(exclude=["metadata"], indent=2)
    else:
        # If it's already a string, use it directly
        merged_json = str(rendered_merged)
    
    # Parse JSON string to dict for counting
    merged_data = json.loads(merged_json)
    merged_counts = count_blocks(merged_data)
    
    # Save outputs
    with open("regular_output.json", "w") as f:
        f.write(regular_json)
    
    with open("merged_output.json", "w") as f:
        f.write(merged_json)
    
    # Compare block counts
    print("\n=== Block Type Counts ===")
    print(f"{'Block Type':<20} {'Regular':<10} {'Merged':<10} {'Difference':<10}")
    print("-" * 60)
    
    all_types = set(regular_counts.keys()) | set(merged_counts.keys())
    for block_type in sorted(all_types):
        regular = regular_counts.get(block_type, 0)
        merged = merged_counts.get(block_type, 0)
        diff = merged - regular
        print(f"{block_type:<20} {regular:<10} {merged:<10} {diff:<10}")
    
    # Total counts
    regular_total = sum(regular_counts.values())
    merged_total = sum(merged_counts.values())
    print(f"\n{'TOTAL':<20} {regular_total:<10} {merged_total:<10} {merged_total - regular_total:<10}")
    
    # Check if any blocks were merged
    if regular_total == merged_total:
        print("\nNo blocks were merged. The outputs are identical.")
    else:
        reduction = ((regular_total - merged_total) / regular_total) * 100
        print(f"\nMerged JSON reduced block count by {reduction:.1f}%")
    
    print("\nOutput files saved:")
    print("  - regular_output.json")
    print("  - merged_output.json")
    
    # Look for merged blocks and debugging info
    print("\n=== Looking for merged blocks ===")
    def find_blocks_info(node, info=None, depth=0):
        if info is None:
            info = {"merged": [], "mergeable_types": {}, "with_children": []}
        
        if isinstance(node, dict):
            block_type = node.get("block_type", "")
            
            # Track block types
            if block_type:
                if block_type not in info["mergeable_types"]:
                    info["mergeable_types"][block_type] = 0
                info["mergeable_types"][block_type] += 1
            
            # Check if this is a merged block
            if node.get("merged_count", 0) > 1:
                info["merged"].append({
                    "type": block_type,
                    "count": node.get("merged_count"),
                    "text": node.get("html", "")[:50] + "..." if node.get("html") else "",
                    "depth": depth
                })
            
            # Check for children_merged indicator
            if "children_merged" in node:
                info["with_children"].append({
                    "type": block_type,
                    "merged": node["children_merged"],
                    "depth": depth
                })
            
            # Check children recursively
            if "children" in node and node["children"]:
                for child in node["children"]:
                    find_blocks_info(child, info, depth + 1)
            
            # Check pages
            if "pages" in node and isinstance(node["pages"], list):
                for page in node["pages"]:
                    find_blocks_info(page, info, depth + 1)
        
        return info
    
    # Regular info
    print("\n--- Regular JSON Structure ---")
    regular_info = find_blocks_info(regular_data)
    print(f"Block type distribution:")
    for block_type, count in sorted(regular_info["mergeable_types"].items()):
        print(f"  {block_type}: {count}")
    
    # Merged info
    print("\n--- Merged JSON Structure ---")
    merged_info = find_blocks_info(merged_data)
    print(f"Block type distribution:")
    for block_type, count in sorted(merged_info["mergeable_types"].items()):
        print(f"  {block_type}: {count}")
    
    if merged_info["merged"]:
        print(f"\nFound {len(merged_info['merged'])} merged blocks:")
        for block in merged_info["merged"]:
            print(f"  - {block['type']} at depth {block['depth']}: merged {block['count']} blocks")
    
    if merged_info["with_children"]:
        print(f"\nFound {len(merged_info['with_children'])} blocks with merged children:")
        for block in merged_info["with_children"]:
            print(f"  - {block['type']} at depth {block['depth']}: {block['merged']} children merged")


if __name__ == "__main__":
    main()