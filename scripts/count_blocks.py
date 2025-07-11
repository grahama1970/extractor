"""
Module: count_blocks.py

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

import json
import sys
from collections import Counter

def count_blocks_in_json(json_path):
    """Count blocks by type in JSON output."""
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    block_counts = Counter()
    tables_info = []
    
    # Handle list format (regular JSON)
    if isinstance(data, list):
        for block in data:
            block_type = block.get('block_type', 'unknown')
            block_counts[block_type] += 1
            
            if block_type == 'Table':
                tables_info.append({
                    'page': block.get('page'),
                    'extraction_method': block.get('extraction_method', 'unknown'),
                    'quality_score': block.get('quality_score'),
                    'cell_count': len(block.get('cells', []))
                })
    
    return block_counts, tables_info

def main():
    json_path = "test_results/current_extraction/2505.03335v2/2505.03335v2.json"
    
    try:
        counts, tables = count_blocks_in_json(json_path)
        
        print("Block counts:")
        for block_type, count in sorted(counts.items()):
            print(f"  {block_type}: {count}")
        
        print(f"\nTotal tables: {counts.get('Table', 0)}")
        
        if tables:
            print("\nTable details:")
            for i, table in enumerate(tables):
                print(f"  Table {i}: Page {table['page']}, Method: {table['extraction_method']}, "
                      f"Quality: {table['quality_score']}, Cells: {table['cell_count']}")
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()