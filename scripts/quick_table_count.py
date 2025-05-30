"""Quick script to count tables in extraction output."""

import json
import os
from pathlib import Path

def count_tables_in_json(json_path):
    """Count tables in JSON output."""
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    table_count = 0
    tables_info = []
    
    # For ArangoDB format
    if 'document' in data and 'blocks' in data['document']:
        blocks = data['document']['blocks']
        for block in blocks:
            if block.get('block_type') == 'Table':
                table_count += 1
                tables_info.append({
                    'page': block.get('page'),
                    'extraction_method': block.get('extraction_method', 'unknown'),
                    'quality_score': block.get('quality_score'),
                    'cell_count': len(block.get('cells', []))
                })
    # For regular JSON format
    elif isinstance(data, list):
        for block in data:
            if block.get('block_type') == 'Table':
                table_count += 1
                tables_info.append({
                    'page': block.get('page'),
                    'extraction_method': block.get('extraction_method', 'unknown'),
                    'quality_score': block.get('quality_score'),
                    'cell_count': len(block.get('cells', []))
                })
    
    return table_count, tables_info

def main():
    # Check our extraction
    our_json = "data/output/2505.03335v2/blocks.json"
    if os.path.exists(our_json):
        count, info = count_tables_in_json(our_json)
        print(f"Our extraction: {count} tables")
        for i, table in enumerate(info):
            print(f"  Table {i}: Page {table['page']}, Method: {table['extraction_method']}, "
                  f"Quality: {table['quality_score']}, Cells: {table['cell_count']}")
    
    # Check if we have any other JSON outputs
    print("\nChecking other JSON outputs...")
    for json_file in Path(".").glob("**/*2505.03335v2*.json"):
        if "blocks.json" not in str(json_file):
            continue
        print(f"\nFile: {json_file}")
        try:
            count, _ = count_tables_in_json(json_file)
            print(f"  Tables: {count}")
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == "__main__":
    main()