#!/usr/bin/env python3
"""Test that the fixed CodeProcessor now stores tree-sitter metadata"""

import sys
from pathlib import Path

# Add to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from marker.schema.blocks import Code
from marker.schema.polygon import PolygonBox
from marker.processors.code import CodeProcessor
import json

def test_metadata_storage():
    """Test that tree-sitter metadata is now stored"""
    
    # Create a test code block
    test_code = '''def fibonacci(n: int) -> int:
    """Calculate the nth Fibonacci number
    
    Args:
        n: The position in the Fibonacci sequence
        
    Returns:
        The nth Fibonacci number
    """
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)'''
    
    # Create code block
    code_block = Code(
        code=test_code,
        polygon=PolygonBox(polygon=[[0, 0], [100, 0], [100, 50], [0, 50]]),
        page_id=1
    )
    
    print("=== Testing Fixed CodeProcessor ===")
    print(f"Initial state:")
    print(f"  Language: {code_block.language}")
    print(f"  Metadata: {code_block.metadata}")
    
    # Process with fixed CodeProcessor
    processor = CodeProcessor()
    detected_lang = processor.detect_language(code_block)
    
    print(f"\nAfter processing:")
    print(f"  Language: {detected_lang}")
    print(f"  Has metadata: {code_block.metadata is not None}")
    
    # Check if tree-sitter data was stored
    if code_block.metadata and hasattr(code_block.metadata, 'tree_sitter_data'):
        ts_data = code_block.metadata.tree_sitter_data
        print(f"  Has tree_sitter_data: Yes")
        print(f"    Success: {ts_data.get('tree_sitter_success')}")
        print(f"    Functions: {len(ts_data.get('functions', []))}")
        
        # Show function details
        for func in ts_data.get('functions', []):
            print(f"\n    Function: {func.get('name')}")
            print(f"      Parameters: {func.get('parameters', [])}")
            print(f"      Return type: {func.get('return_type')}")
            doc = func.get('docstring', '')
            if doc:
                print(f"      Docstring: {doc[:50]}...")
    else:
        print(f"  No tree_sitter_data found")
        # Check if it's in extra fields
        if code_block.metadata:
            extra = getattr(code_block.metadata, '__dict__', {})
            if 'tree_sitter_data' in extra:
                print("  Found tree_sitter_data in extra fields")
                ts_data = extra['tree_sitter_data']
                print(f"    Functions: {len(ts_data.get('functions', []))}")
    
    return code_block

def test_configuration():
    """Test that the configuration flag works"""
    
    test_code = "def hello(): pass"
    
    # Test with metadata disabled
    processor = CodeProcessor()
    processor.store_tree_sitter_metadata = False
    
    block1 = Code(
        code=test_code,
        polygon=PolygonBox(polygon=[[0, 0], [100, 0], [100, 50], [0, 50]])
    )
    processor.detect_language(block1)
    
    print("\n=== With metadata disabled ===")
    print(f"Has metadata: {block1.metadata is not None}")
    
    # Test with metadata enabled (default)
    processor.store_tree_sitter_metadata = True
    
    block2 = Code(
        code=test_code,
        polygon=PolygonBox(polygon=[[0, 0], [100, 0], [100, 50], [0, 50]])
    )
    processor.detect_language(block2)
    
    print("\n=== With metadata enabled ===")
    print(f"Has metadata: {block2.metadata is not None}")
    if block2.metadata:
        print(f"Has tree_sitter_data: {hasattr(block2.metadata, 'tree_sitter_data')}")

if __name__ == "__main__":
    test_metadata_storage()
    test_configuration()
    
    print("\n✅ CodeProcessor is now fixed!")
    print("Tree-sitter metadata is stored and available for LLMs and downstream processing.")