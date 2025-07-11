"""
Module: demo_summarizer.py

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

#!/usr/bin/env python3
"""
Demo script to compare regular JSON vs merged JSON output
and summarize the differences.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List


def run_conversion(pdf_path: str, output_format: str) -> Dict:
    """Run the CLI conversion and return JSON data."""
    output_file = f"output_{output_format}.json"
    # Remove output file if it exists
    Path(output_file).unlink(missing_ok=True)
    
    cmd = [
        "python", "cli.py", "convert", "single", pdf_path,
        "--output-format", output_format,
        "--output-dir", "."
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error running command: {' '.join(cmd)}")
        print(f"Error: {result.stderr}")
        sys.exit(1)
    
    # The CLI writes to a file named after the PDF basename
    base_name = Path(pdf_path).stem
    json_file = Path(f"./{base_name}.json")
    
    if not json_file.exists():
        print(f"Expected output file not found: {json_file}")
        sys.exit(1)
    
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Rename for clarity
    json_file.rename(output_file)
    
    return data


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


def compare_outputs(pdf_path: str):
    """Compare regular JSON vs merged JSON output."""
    print(f"Processing: {pdf_path}\n")
    
    # Run regular JSON conversion
    print("Running regular JSON conversion...")
    regular_json = run_conversion(pdf_path, "json")
    regular_counts = count_blocks(regular_json)
    
    # Run merged JSON conversion
    print("Running merged JSON conversion...")
    merged_json = run_conversion(pdf_path, "merged-json")
    merged_counts = count_blocks(merged_json)
    
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
        
    # Show some example merged blocks
    print("\n=== Example of Merged Text Blocks ===")
    # Find first Text block in merged output that has merged_count > 1
    def find_merged_text(node):
        if isinstance(node, dict):
            # Check if this is a merged text block
            if (node.get("block_type") in ["Text", "Line", "Span"] and 
                node.get("merged_count", 1) > 1):
                return node
            # Check children
            if "children" in node and node["children"]:
                for child in node["children"]:
                    result = find_merged_text(child)
                    if result:
                        return result
            # Check pages
            if "pages" in node and isinstance(node["pages"], list):
                for page in node["pages"]:
                    result = find_merged_text(page)
                    if result:
                        return result
        return None
    
    merged_example = find_merged_text(merged_json)
    if merged_example:
        print(f"Found merged {merged_example['block_type']} block:")
        print(f"  Merged count: {merged_example.get('merged_count', 'N/A')}")
        if "html" in merged_example:
            print(f"  HTML content: {merged_example['html'][:100]}...")
    else:
        print("No merged text blocks found in output.")
    
    print("\nOutput files saved:")
    print("  - output_json.json (regular JSON)")
    print("  - output_merged-json.json (merged JSON)")


if __name__ == "__main__":
    # Test with a document that has more text content
    pdf_path = "./repos/camelot/docs/_static/pdf/column_separators.pdf"
    compare_outputs(pdf_path)