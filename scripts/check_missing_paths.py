"""Check what's at the paths where tables are missing."""
import json
from pathlib import Path


def get_element_at_path(data, path):
    """Navigate to a specific path in the JSON structure."""
    parts = path.split('/')
    current = data
    
    for part in parts[1:]:  # Skip 'root'
        if '[' in part:
            # Handle array indices
            key, index = part.split('[')
            index = int(index.rstrip(']'))
            if key:
                current = current.get(key, [])
            if isinstance(current, list) and index < len(current):
                current = current[index]
            else:
                return None
        else:
            current = current.get(part)
            if current is None:
                return None
    
    return current


def main():
    """Check what elements exist at the missing table paths."""
    baseline_path = Path("baseline_test/baseline_output/2505.03335v2/2505.03335v2.json")
    current_path = Path("test_results/with_metadata/2505.03335v2/2505.03335v2.json")
    
    with open(baseline_path) as f:
        baseline_data = json.load(f)
    
    with open(current_path) as f:
        current_data = json.load(f)
    
    # Check missing paths
    missing_paths = [
        "root/children[11]/children[0]",
        "root/children[21]/children[0]"
    ]
    
    for path in missing_paths:
        print(f"\n=== Checking path: {path} ===")
        
        # Get baseline element
        baseline_elem = get_element_at_path(baseline_data, path)
        if baseline_elem:
            print(f"Baseline: {baseline_elem.get('block_type')} block")
            print(f"  BBox: {baseline_elem.get('bbox')}")
            print(f"  Text: {(baseline_elem.get('text_content') or '')[:100]}...")
        
        # Get current element
        current_elem = get_element_at_path(current_data, path)
        if current_elem:
            print(f"Current: {current_elem.get('block_type')} block")
            print(f"  BBox: {current_elem.get('bbox')}")
            print(f"  Text: {(current_elem.get('text_content') or '')[:100]}...")
        else:
            # Check parent
            parent_path = '/'.join(path.split('/')[:-1])
            parent = get_element_at_path(current_data, parent_path)
            if parent:
                print(f"Current parent has {len(parent.get('children', []))} children")
                if parent.get('children'):
                    print("Current children types:")
                    for i, child in enumerate(parent['children']):
                        print(f"  [{i}]: {child.get('block_type')}")
    
    # Also check the 11th and 21st children in current to see what they contain
    print("\n=== Checking children[11] and children[21] in current ===")
    for idx in [11, 21]:
        elem = current_data.get('children', [])[idx] if idx < len(current_data.get('children', [])) else None
        if elem:
            print(f"\nchildren[{idx}]:")
            print(f"  Type: {elem.get('block_type')}")
            print(f"  Children count: {len(elem.get('children', []))}")
            if elem.get('children'):
                print("  Child types:")
                for i, child in enumerate(elem['children'][:3]):  # First 3 children
                    print(f"    [{i}]: {child.get('block_type')}")


if __name__ == "__main__":
    main()