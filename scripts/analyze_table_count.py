"""Analyze table count differences more carefully."""
import json
from pathlib import Path


def bbox_overlap(bbox1, bbox2, threshold=0.8):
    """Check if two bboxes overlap significantly."""
    if not bbox1 or not bbox2:
        return False
    
    # Calculate intersection
    x1 = max(bbox1[0], bbox2[0])
    y1 = max(bbox1[1], bbox2[1])
    x2 = min(bbox1[2], bbox2[2])
    y2 = min(bbox1[3], bbox2[3])
    
    if x2 < x1 or y2 < y1:
        return False
    
    intersection = (x2 - x1) * (y2 - y1)
    area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
    area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
    
    # Check if intersection is significant relative to either bbox
    return (intersection / area1 > threshold) or (intersection / area2 > threshold)


def extract_all_tables(data, tables=None, path="root"):
    """Extract all tables from the JSON structure."""
    if tables is None:
        tables = []
    
    if isinstance(data, dict):
        if data.get('block_type') == 'Table':
            tables.append({
                'path': path,
                'bbox': data.get('bbox'),
                'page_idx': data.get('page_idx'),
                'text': (data.get('text_content', '') or '')[:200],
                'children_count': len(data.get('children', [])),
            })
        
        # Check children
        for key, value in data.items():
            if key == 'children' and isinstance(value, list):
                for i, child in enumerate(value):
                    extract_all_tables(child, tables, f"{path}/children[{i}]")
            elif isinstance(value, (dict, list)):
                extract_all_tables(value, tables, f"{path}/{key}")
    
    elif isinstance(data, list):
        for i, item in enumerate(data):
            extract_all_tables(item, tables, f"{path}[{i}]")
    
    return tables


def main():
    """Compare table counts and find matches."""
    # Load files
    baseline_path = Path("baseline_test/baseline_output/2505.03335v2/2505.03335v2.json")
    current_path = Path("test_results/with_metadata/2505.03335v2/2505.03335v2.json")
    
    with open(baseline_path) as f:
        baseline_data = json.load(f)
    
    with open(current_path) as f:
        current_data = json.load(f)
    
    # Extract tables
    baseline_tables = extract_all_tables(baseline_data)
    current_tables = extract_all_tables(current_data)
    
    print(f"Baseline: {len(baseline_tables)} tables")
    print(f"Current: {len(current_tables)} tables")
    print(f"Difference: {len(baseline_tables) - len(current_tables)}")
    
    # Match tables based on location
    matched = []
    unmatched_baseline = []
    
    for i, b_table in enumerate(baseline_tables):
        found_match = False
        for j, c_table in enumerate(current_tables):
            if bbox_overlap(b_table['bbox'], c_table['bbox']):
                matched.append((i, j))
                found_match = True
                break
        
        if not found_match:
            unmatched_baseline.append(i)
    
    print(f"\nMatched tables: {len(matched)}")
    print(f"Unmatched baseline tables: {len(unmatched_baseline)}")
    
    # Show unmatched tables
    if unmatched_baseline:
        print("\n=== MISSING TABLES ===")
        for idx in unmatched_baseline:
            table = baseline_tables[idx]
            print(f"\nMissing Table {idx + 1}:")
            print(f"  Path: {table['path']}")
            print(f"  BBox: {table['bbox']}")
            print(f"  Children: {table['children_count']}")
            print(f"  Text preview: {table['text'][:100]}...")
    
    # Check paths of missing tables to find patterns
    print("\n=== PATH ANALYSIS ===")
    baseline_paths = [t['path'] for t in baseline_tables]
    current_paths = [t['path'] for t in current_tables]
    
    # Find common path prefixes that are missing
    missing_prefixes = set()
    for idx in unmatched_baseline:
        path = baseline_tables[idx]['path']
        # Extract the main path component
        parts = path.split('/')
        if len(parts) > 2:
            prefix = '/'.join(parts[:3])
            missing_prefixes.add(prefix)
    
    print(f"\nMissing table path prefixes: {missing_prefixes}")


if __name__ == "__main__":
    main()