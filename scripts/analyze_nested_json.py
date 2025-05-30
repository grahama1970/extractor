"""Analyze nested JSON structure."""

import json
from collections import Counter

def count_blocks_recursive(data, block_counts=None, tables_info=None, depth=0):
    """Recursively count blocks in nested structure."""
    if block_counts is None:
        block_counts = Counter()
    if tables_info is None:
        tables_info = []
    
    if isinstance(data, dict):
        block_type = data.get('block_type')
        if block_type:
            block_counts[block_type] += 1
            
            if block_type == 'Table':
                tables_info.append({
                    'page': data.get('page', 'unknown'),
                    'extraction_method': data.get('extraction_method', 'unknown'),
                    'quality_score': data.get('quality_score'),
                    'cell_count': len(data.get('cells', [])),
                    'data': data
                })
        
        # Check children
        if 'children' in data and data['children']:
            for child in data['children']:
                count_blocks_recursive(child, block_counts, tables_info, depth+1)
                
    elif isinstance(data, list):
        for item in data:
            count_blocks_recursive(item, block_counts, tables_info, depth)
    
    return block_counts, tables_info

def main():
    json_path = "test_results/current_extraction/2505.03335v2/2505.03335v2.json"
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    counts, tables = count_blocks_recursive(data)
    
    print("Block counts:")
    for block_type, count in sorted(counts.items()):
        print(f"  {block_type}: {count}")
    
    print(f"\nTotal tables: {counts.get('Table', 0)}")
    
    if tables:
        print("\nTable details:")
        for i, table in enumerate(tables):
            print(f"  Table {i}: Page {table['page']}, Method: {table['extraction_method']}, "
                  f"Quality: {table['quality_score']}, Cells: {table['cell_count']}")
    else:
        # Check for table-like structures
        print("\nSearching for table-like content...")
        if 'TableCell' in counts:
            print(f"  Found {counts['TableCell']} TableCell blocks")
        
        # Sample some text to see if tables might be misclassified
        print("\nSampling Text blocks on pages where we expect tables (9, 10, 11)...")
        text_samples = []
        
        def find_text_on_pages(data, target_pages, samples, path=""):
            if isinstance(data, dict):
                page = data.get('page', -1)
                if data.get('block_type') == 'Text' and page in target_pages:
                    text = data.get('text', '')[:100]
                    samples.append(f"Page {page}: {text}...")
                if 'children' in data:
                    for child in data['children']:
                        find_text_on_pages(child, target_pages, samples, path + "/" + str(data.get('block_type', '')))
            elif isinstance(data, list):
                for item in data:
                    find_text_on_pages(item, target_pages, samples, path)
        
        find_text_on_pages(data, [9, 10, 11], text_samples)
        for sample in text_samples[:10]:
            print(f"  {sample}")

if __name__ == "__main__":
    main()