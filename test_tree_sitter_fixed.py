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
        '''def func(inputs: Union[str, List[str]],
         enabled: Dict[str, bool]) -> Iterable[str]:
    """Process inputs based on enabled flags
    
    Args:
        inputs: Input names to process
        enabled: Mapping of input names to enabled status
        
    Returns:
        Iterator of enabled input names
    """
    return [i for i in inputs if enabled.get(i, False)]''',
        
        '''class TypeChecker:
    """A class for type checking operations"""
    
    def __init__(self, strict: bool = False):
        """Initialize the type checker
        
        Args:
            strict: Whether to use strict type checking
        """
        self.strict = strict
    
    def check(self, value: Any, expected_type: type) -> bool:
        """Check if value matches expected type
        
        Args:
            value: Value to check
            expected_type: Expected type
            
        Returns:
            Whether the value matches the type
        """
        return isinstance(value, expected_type)'''
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
            docstring = func.get('docstring')
            if docstring:
                print(f"    Docstring: {docstring[:50]}...")
            else:
                print(f"    Docstring: None")
            
        for cls in metadata.get('classes', []):
            print(f"\n  Class: {cls['name']}")
            docstring = cls.get('docstring')
            if docstring:
                print(f"    Docstring: {docstring[:50]}...")
            else:
                print(f"    Docstring: None")
            methods = cls.get('methods', [])
            if methods:
                print(f"    Methods: {[m.get('name', 'unnamed') for m in methods]}")
            else:
                print(f"    Methods: []")
        
        results.append({
            "code": code,
            "metadata": metadata
        })
    
    return results

def check_actual_marker_extraction():
    """Check what's actually being stored in marker documents"""
    
    pdf_path = "data/input/python-type-checking-readthedocs-io-en-latest.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        return
    
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
    
    print(f"Found {len(code_blocks)} code blocks on page 7")
    
    for i, block in enumerate(code_blocks):
        print(f"\nCode Block {i+1}:")
        print(f"  Language: {getattr(block, 'language', 'None')}")
        code = getattr(block, 'code', '')
        print(f"  Code: {code[:100]}...")
        
        # Check if block has metadata
        if hasattr(block, 'metadata') and block.metadata:
            print(f"  Metadata: {block.metadata}")
        else:
            print("  Metadata: None")
            
        # Check for tree-sitter metadata attributes
        tree_sitter_attrs = ['functions', 'classes', 'parameters', 'docstring', 'tree_sitter_metadata', 'code_metadata']
        found_attrs = []
        for attr in tree_sitter_attrs:
            if hasattr(block, attr):
                value = getattr(block, attr)
                if value:
                    found_attrs.append(f"{attr}: {value}")
        
        if found_attrs:
            print("  Tree-sitter attributes found:")
            for attr in found_attrs:
                print(f"    {attr}")
        else:
            print("  No tree-sitter attributes found")
        
        # Run tree-sitter manually on the code
        if code and hasattr(block, 'language'):
            metadata = extract_code_metadata(code, block.language)
            print(f"\n  Manual tree-sitter extraction:")
            print(f"    Functions: {len(metadata.get('functions', []))}")
            print(f"    Classes: {len(metadata.get('classes', []))}")
            
            # Show what SHOULD be extracted
            for func in metadata.get('functions', []):
                print(f"    Function '{func['name']}' with {len(func.get('parameters', []))} params")
                if func.get('docstring'):
                    print(f"      Docstring: Yes")
            
def inspect_code_processor():
    """Inspect how CodeProcessor uses tree-sitter"""
    
    print("\n=== Inspecting CodeProcessor ===")
    
    # Look at CodeProcessor to see if it stores metadata
    processor = CodeProcessor()
    
    # Create a mock code block
    from marker.schema.blocks import Code
    from marker.schema.polygon import PolygonBox
    
    test_code = '''def example(x: int, y: str) -> bool:
    """Example function with types"""
    return True'''
    
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
    print("\nAttributes on code block:")
    standard_attrs = ['code', 'language', 'polygon', 'id', 'block_type']
    metadata_attrs = []
    
    for attr in dir(code_block):
        if not attr.startswith('_') and hasattr(code_block, attr):
            value = getattr(code_block, attr)
            if not callable(value) and attr not in standard_attrs:
                metadata_attrs.append(f"{attr}: {str(value)[:100]}")
    
    if metadata_attrs:
        print("  Additional metadata:")
        for attr in metadata_attrs:
            print(f"    {attr}")
    else:
        print("  No additional metadata attributes found")

def check_code_block_schema():
    """Check the Code block schema definition"""
    print("\n=== Code Block Schema ===")
    
    from marker.schema.blocks import Code
    
    # Check what fields are defined in the schema
    print("Code block model fields:")
    for field_name, field_info in Code.model_fields.items():
        print(f"  {field_name}: {field_info.annotation}")
    
    # Check if there's a place for metadata
    if 'metadata' in Code.model_fields:
        print("\n  Code block HAS a metadata field!")
    else:
        print("\n  Code block LACKS a metadata field for tree-sitter data")

def main():
    # Test what tree-sitter can extract
    print("=== Testing Tree-Sitter Capabilities ===")
    tree_sitter_results = test_tree_sitter_extraction()
    
    # Check the schema
    check_code_block_schema()
    
    # Check what marker actually extracts
    check_actual_marker_extraction()
    
    # Inspect the code processor
    inspect_code_processor()
    
    # Save results
    output_dir = "test_results/tree_sitter_analysis"
    os.makedirs(output_dir, exist_ok=True)
    
    with open(os.path.join(output_dir, "tree_sitter_capabilities.json"), "w") as f:
        json.dump(tree_sitter_results, f, indent=2, default=str)
    
    print(f"\n=== Analysis Complete ===")
    print(f"Results saved to {output_dir}")

if __name__ == "__main__":
    main()