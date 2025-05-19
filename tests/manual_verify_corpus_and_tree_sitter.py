#!/usr/bin/env python3
"""
Manual verification script for corpus generator and tree-sitter integration.
This script tests:
1. PyMuPDF corpus validation
2. Camelot table extraction fallback
3. Tree-sitter code language detection
"""

import sys
import os
from pathlib import Path

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from marker.scripts.convert_for_qa import convert_single_pdf
from marker.services.utils.tree_sitter_utils import extract_code_metadata, get_supported_language
from marker.processors.code import CodeProcessor
from marker.schema.blocks import Code
from marker.schema.document import Document

def test_corpus_validation():
    """Test corpus validation with PyMuPDF"""
    print("\n=== Testing Corpus Validation ===")
    
    # Test PDF path
    test_pdf = "data/input/2505.03335v2.pdf"
    if not os.path.exists(test_pdf):
        print(f"Error: Test PDF not found at {test_pdf}")
        return False
    
    try:
        # Run Q&A optimized conversion
        output_path = convert_single_pdf(
            pdf_path=test_pdf,
            output_dir="test_results/corpus_validation",
            page_range="0-2"
        )
        
        print(f"✓ Conversion completed: {output_path}")
        
        # Check if validation data is included
        with open(output_path, 'r') as f:
            content = f.read()
            if "validation" in content.lower():
                print("✓ Validation data found in output")
            else:
                print("✗ Validation data not found in output")
                
        return True
        
    except Exception as e:
        print(f"✗ Error during corpus validation: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_tree_sitter_detection():
    """Test tree-sitter code language detection"""
    print("\n=== Testing Tree-Sitter Code Detection ===")
    
    # Test code snippets
    test_cases = [
        ("python", """
def hello_world():
    print("Hello, World!")
    return 42
"""),
        ("javascript", """
const greet = (name) => {
    console.log(`Hello, ${name}!`);
    return name.length;
};
"""),
        ("java", """
public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
    }
}
"""),
    ]
    
    processor = CodeProcessor()
    success_count = 0
    
    for expected_lang, code in test_cases:
        print(f"\nTesting {expected_lang} detection...")
        
        # Create a mock Code block
        code_block = Code()
        code_block.code = code
        
        # Detect language
        detected = processor.detect_language(code_block)
        
        if detected == expected_lang:
            print(f"✓ Correctly detected as {detected}")
            success_count += 1
        else:
            print(f"✗ Expected {expected_lang}, got {detected}")
            
        # Also test direct metadata extraction
        supported_lang = get_supported_language(expected_lang)
        if supported_lang:
            metadata = extract_code_metadata(code, expected_lang)
            if metadata.get('tree_sitter_success'):
                print(f"✓ Metadata extraction successful")
                if metadata.get('functions'):
                    print(f"  Found {len(metadata['functions'])} functions")
                if metadata.get('classes'):
                    print(f"  Found {len(metadata['classes'])} classes")
            else:
                print(f"✗ Metadata extraction failed: {metadata.get('error')}")
        else:
            print(f"✗ Language {expected_lang} not supported by tree-sitter")
    
    print(f"\n{success_count}/{len(test_cases)} tests passed")
    return success_count == len(test_cases)

def test_camelot_fallback():
    """Test Camelot table extraction fallback"""
    print("\n=== Testing Camelot Fallback ===")
    
    try:
        from marker.processors.table import CAMELOT_AVAILABLE
        if not CAMELOT_AVAILABLE:
            print("✗ Camelot is not available")
            print("  Install with: pip install camelot-py opencv-python-headless")
            return False
            
        print("✓ Camelot is available")
        
        # Try to import and test basic functionality
        import camelot
        
        test_pdf = "data/input/2505.03335v2.pdf"
        if os.path.exists(test_pdf):
            tables = camelot.read_pdf(test_pdf, pages="1", flavor="lattice")
            print(f"✓ Camelot extracted {len(tables)} tables from test PDF")
            return True
        else:
            print("✗ Test PDF not found")
            return False
            
    except Exception as e:
        print(f"✗ Error testing Camelot: {e}")
        return False

def main():
    """Run all verification tests"""
    print("=== Corpus Generator and Tree-Sitter Verification ===")
    
    results = {
        "Corpus Validation": test_corpus_validation(),
        "Tree-Sitter Detection": test_tree_sitter_detection(),
        "Camelot Fallback": test_camelot_fallback()
    }
    
    print("\n=== Summary ===")
    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    if all_passed:
        print("\n✓ All tests passed!")
    else:
        print("\n✗ Some tests failed")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())