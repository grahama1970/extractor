#!/usr/bin/env python3
"""
Demonstrate that tree-sitter metadata is NOT being stored in code blocks
"""

import sys
from pathlib import Path

# Add to path
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from marker.schema.blocks import Code
from marker.schema.polygon import PolygonBox
from marker.processors.code import CodeProcessor
from marker.services.utils.tree_sitter_utils import extract_code_metadata

def main():
    # Create a code block with rich Python code
    test_code = '''def calculate_statistics(data: List[float], 
                        include_outliers: bool = True) -> Dict[str, float]:
    """Calculate basic statistics for a dataset.
    
    Args:
        data: List of numerical values
        include_outliers: Whether to include outliers in calculations
        
    Returns:
        Dictionary containing mean, median, std_dev
    """
    if not data:
        return {"mean": 0.0, "median": 0.0, "std_dev": 0.0}
    
    # Calculate mean
    mean = sum(data) / len(data)
    
    # Calculate median
    sorted_data = sorted(data)
    n = len(sorted_data)
    median = sorted_data[n//2] if n % 2 else (sorted_data[n//2-1] + sorted_data[n//2]) / 2
    
    # Calculate standard deviation
    variance = sum((x - mean) ** 2 for x in data) / len(data)
    std_dev = variance ** 0.5
    
    return {"mean": mean, "median": median, "std_dev": std_dev}'''
    
    # Create code block
    code_block = Code(
        code=test_code,
        polygon=PolygonBox(polygon=[[0, 0], [100, 0], [100, 50], [0, 50]]),
        page_id=1
    )
    
    print("=== Before Processing ===")
    print(f"Language: {code_block.language}")
    print(f"Metadata: {code_block.metadata}")
    
    # Process with CodeProcessor
    processor = CodeProcessor()
    processor.detect_language(code_block)
    
    print("\n=== After Processing ===")
    print(f"Language: {code_block.language}")
    print(f"Metadata: {code_block.metadata}")
    
    # Show what tree-sitter COULD extract
    metadata = extract_code_metadata(test_code, "python")
    
    print("\n=== What Tree-Sitter Can Extract ===")
    print(f"Successful: {metadata.get('tree_sitter_success')}")
    print(f"Functions: {len(metadata.get('functions', []))}")
    
    for func in metadata.get('functions', []):
        print(f"\nFunction: {func['name']}")
        print(f"  Parameters: {len(func.get('parameters', []))} found")
        for param in func.get('parameters', []):
            print(f"    - {param['name']}: {param.get('type', 'Any')}")
        print(f"  Return type: {func.get('return_type', 'Any')}")
        doc = func.get('docstring', '')
        if doc:
            print(f"  Docstring: {doc[:50]}...")
    
    print("\n=== The Problem ===")
    print("Tree-sitter extracted rich metadata (parameters, types, docstrings)")
    print("but CodeProcessor only uses it for language detection scoring.")
    print("The metadata is NOT stored on the code block for downstream use!")
    
    # Show what SHOULD be stored
    print("\n=== What Should Be Stored ===")
    print("code_block.tree_sitter_metadata = {")
    print("    'functions': [...],")
    print("    'classes': [...],")
    print("    'language': 'python',")
    print("    'success': True")
    print("}")
    
    return metadata

if __name__ == "__main__":
    result = main()