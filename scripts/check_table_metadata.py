"""
Module: check_table_metadata.py

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

import json

def find_tables_with_metadata(data, path=""):
    """Recursively find tables and check their metadata."""
    tables = []
    
    if isinstance(data, dict):
        if data.get('block_type') == 'Table':
            table_info = {
                'path': path,
                'id': data.get('id'),
                'extraction_method': data.get('extraction_method'),
                'extraction_details': data.get('extraction_details'),
                'quality_score': data.get('quality_score'),
                'has_cells': 'children' in data and any(
                    child.get('block_type') == 'TableCell' 
                    for child in data.get('children', [])
                    if isinstance(child, dict)
                )
            }
            tables.append(table_info)
        
        # Recurse into children
        if 'children' in data and data['children'] is not None:
            for i, child in enumerate(data['children']):
                tables.extend(find_tables_with_metadata(child, f"{path}/children[{i}]"))
                
    elif isinstance(data, list):
        for i, item in enumerate(data):
            tables.extend(find_tables_with_metadata(item, f"{path}[{i}]"))
    
    return tables

def main():
    json_path = "test_results/with_metadata/2505.03335v2/2505.03335v2.json"
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    tables = find_tables_with_metadata(data)
    
    print(f"Found {len(tables)} tables")
    print("\nTable metadata status:")
    
    for i, table in enumerate(tables):
        print(f"\nTable {i}:")
        print(f"  ID: {table['id']}")
        print(f"  Has cells: {table['has_cells']}")
        print(f"  Extraction method: {table['extraction_method']}")
        print(f"  Extraction details: {table['extraction_details']}")
        print(f"  Quality score: {table['quality_score']}")
        
    # Summary
    tables_with_method = sum(1 for t in tables if t['extraction_method'] is not None)
    print(f"\nSummary:")
    print(f"  Tables with extraction method: {tables_with_method}/{len(tables)}")

if __name__ == "__main__":
    main()