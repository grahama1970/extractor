#!/usr/bin/env python3
"""
Test what tree-sitter is actually extracting from code blocks
"""

import os
import sys
import json
from pathlib import Path

# Ensure we're running from the project root
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.schema import BlockTypes
from marker.services.utils.tree_sitter_utils import extract_code_metadata
from marker.processors.code import CodeProcessor

def test_tree_sitter_extraction():
    """Test what tree-sitter extracts from code"""
    
    # Example code block from the PDF
    code_samples = [
        """def func(inputs: Union[str, List[str]],
         enabled: Dict[str, bool]) -> Iterable[str]:
    \"\"\"Process inputs based on enabled flags
    
    Args:
        inputs: Input names to process
        enabled: Mapping of input names to enabled status
        
    Returns:
        Iterator of enabled input names
    \"\"\"
    return [i for i in inputs if enabled.get(i, False)]""",
        
        """class TypeChecker:
    \"\"\"A class for type checking operations\"\"\"
    
    def __init__(self, strict: bool = False):
        \"\"\"Initialize the type checker
        
        Args:
            strict: Whether to use strict type checking
        \"\"\"
        self.strict = strict
    
    def check(self, value: Any, expected_type: type) -> bool:
        \"\"\"Check if value matches expected type
        
        Args:
            value: Value to check
            expected_type: Expected type
            
        Returns:
            Whether the value matches the type
        \"\"\"
        return isinstance(value, expected_type)"""
    ]
    
    results = []
    
    for i, code in enumerate(code_samples):
        print(f"\n=== Testing Code Sample {i+1} ===")
        print("Code snippet:")
        print(code[:100] + "..." if len(code) > 100 else code)
        
        # Extract metadata using tree-sitter
        metadata = extract_code_metadata(code, "python")
        
        print("\nTree-sitter extracted:")
        print(f"  Success: {metadata.get('tree_sitter_success')}")
        print(f"  Functions: {len(metadata.get('functions', []))}")
        print(f"  Classes: {len(metadata.get('classes', []))}")
        
        # Show detailed extraction
        for func in metadata.get('functions', []):
            print(f"\n  Function: {func['name']}")
            print(f"    Parameters: {func.get('parameters', [])}")
            print(f"    Return type: {func.get('return_type')}")
            print(f"    Docstring: {func.get('docstring', '')[:50]}...")
            
        for cls in metadata.get('classes', []):
            print(f"\n  Class: {cls['name']}")
            print(f"    Docstring: {cls.get('docstring', '')[:50]}...")
            print(f"    Methods: {[m.get('name', 'unnamed') for m in cls.get('methods', [])]}")
        
        results.append({
            "code": code,
            "metadata": metadata
        })
    
    return results

def check_actual_marker_extraction():
    """Check what's actually being stored in marker documents"""
    
    pdf_path = "data/input/python-type-checking-readthedocs-io-en-latest.pdf"
    
    # Create a simple converter to check one page
    config = {
        "page_range": range(7, 8),  # Just page 7
        "disable_tqdm": True,
    }
    
    print("\n=== Checking Actual Marker Document ===")
    
    converter = PdfConverter(
        artifact_dict=create_model_dict(),
        config=config
    )
    
    document = converter.build_document(pdf_path)
    
    # Find code blocks
    code_blocks = document.contained_blocks((BlockTypes.Code,))
    
    for i, block in enumerate(code_blocks):
        print(f"\nCode Block {i+1}:")
        print(f"  Language: {getattr(block, 'language', 'None')}")
        print(f"  Code: {getattr(block, 'code', '')[:100]}...")
        
        # Check if block has metadata
        if hasattr(block, 'metadata'):
            print(f"  Metadata: {block.metadata}")
        else:
            print("  Metadata: None")
            
        # Check for tree-sitter metadata attributes
        tree_sitter_attrs = ['functions', 'classes', 'parameters', 'docstring', 'tree_sitter_metadata']
        for attr in tree_sitter_attrs:
            if hasattr(block, attr):
                print(f"  {attr}: {getattr(block, attr)}")
        
        # Run tree-sitter manually on the code
        if hasattr(block, 'code') and hasattr(block, 'language'):
            metadata = extract_code_metadata(block.code, block.language)
            print(f"\n  Manual tree-sitter extraction:")
            print(f"    Functions: {len(metadata.get('functions', []))}")
            print(f"    Classes: {len(metadata.get('classes', []))}")
            
def inspect_code_processor():
    """Inspect how CodeProcessor uses tree-sitter"""
    
    print("\n=== Inspecting CodeProcessor ===")
    
    # Look at CodeProcessor to see if it stores metadata
    processor = CodeProcessor()
    
    # Create a mock code block
    from marker.schema.blocks import Code
    from marker.schema.polygon import PolygonBox
    
    test_code = """def example(x: int, y: str) -> bool:
    \"\"\"Example function with types\"\"\"
    return True"""
    
    code_block = Code(
        code=test_code,
        polygon=PolygonBox(polygon=[[0, 0], [100, 0], [100, 50], [0, 50]])
    )
    
    # Process it
    processor.detect_language(code_block)
    
    print(f"Code block after processing:")
    print(f"  Language: {code_block.language}")
    print(f"  Code: {code_block.code[:50]}...")
    
    # Check all attributes
    print("\nAll attributes on code block:")
    for attr in dir(code_block):
        if not attr.startswith('_') and hasattr(code_block, attr):
            value = getattr(code_block, attr)
            if not callable(value):
                print(f"  {attr}: {str(value)[:100]}")

def main():
    # Test what tree-sitter can extract
    print("=== Testing Tree-Sitter Capabilities ===")
    tree_sitter_results = test_tree_sitter_extraction()
    
    # Check what marker actually extracts
    check_actual_marker_extraction()
    
    # Inspect the code processor
    inspect_code_processor()
    
    # Save results
    output_dir = "test_results/tree_sitter_analysis"
    os.makedirs(output_dir, exist_ok=True)
    
    with open(os.path.join(output_dir, "tree_sitter_capabilities.json"), "w") as f:
        json.dump(tree_sitter_results, f, indent=2)
    
    print(f"\n=== Analysis Complete ===")
    print(f"Results saved to {output_dir}")

if __name__ == "__main__":
    main()