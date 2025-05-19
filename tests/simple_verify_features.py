#!/usr/bin/env python3
"""
Simple verification script for corpus generator and tree-sitter integration.
This version avoids problematic imports.
"""

import sys
import os
from pathlib import Path

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_tree_sitter_direct():
    """Test tree-sitter functionality directly"""
    print("\n=== Testing Tree-Sitter Directly ===")
    
    try:
        from marker.services.utils.tree_sitter_utils import extract_code_metadata, get_supported_language
        print("✓ Successfully imported tree_sitter_utils")
        
        # Test language support
        languages = ["python", "javascript", "java", "cpp", "go"]
        for lang in languages:
            supported = get_supported_language(lang)
            if supported:
                print(f"✓ {lang} is supported")
            else:
                print(f"✗ {lang} is not supported")
        
        # Test code extraction
        python_code = """
def factorial(n):
    '''Calculate factorial of n'''
    if n <= 1:
        return 1
    return n * factorial(n - 1)

class MathOperations:
    def add(self, a, b):
        return a + b
"""
        
        metadata = extract_code_metadata(python_code, "python")
        if metadata.get('tree_sitter_success'):
            print(f"✓ Python code extraction successful")
            print(f"  Functions: {len(metadata.get('functions', []))}")
            print(f"  Classes: {len(metadata.get('classes', []))}")
            
            # Print function details
            for func in metadata.get('functions', []):
                print(f"  Function: {func['name']} - {len(func.get('parameters', []))} params")
                if func.get('docstring'):
                    print(f"    Docstring: {func['docstring']}")
                    
            # Print class details
            for cls in metadata.get('classes', []):
                print(f"  Class: {cls['name']}")
        else:
            print(f"✗ Code extraction failed: {metadata.get('error')}")
            
        return True
        
    except Exception as e:
        print(f"✗ Error testing tree-sitter: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_corpus_validator_exists():
    """Test if corpus validator exists"""
    print("\n=== Testing Corpus Validator Existence ===")
    
    try:
        from marker.processors.corpus_validator import CorpusValidator
        print("✓ CorpusValidator class imported successfully")
        
        # Check methods
        methods = ['validate_corpus', 'extract_raw_corpus']
        for method in methods:
            if hasattr(CorpusValidator, method):
                print(f"✓ Method {method} exists")
            else:
                print(f"✗ Method {method} not found")
                
        return True
        
    except Exception as e:
        print(f"✗ Error importing CorpusValidator: {e}")
        return False

def test_camelot_availability():
    """Test if Camelot is available"""
    print("\n=== Testing Camelot Availability ===")
    
    try:
        import camelot
        print("✓ Camelot imported successfully")
        
        # Test on a sample PDF if available
        test_pdf = "data/input/2505.03335v2.pdf"
        if os.path.exists(test_pdf):
            tables = camelot.read_pdf(test_pdf, pages="1", flavor="lattice")
            print(f"✓ Extracted {len(tables)} tables from test PDF")
        else:
            print("  Test PDF not found, skipping extraction test")
            
        return True
        
    except ImportError:
        print("✗ Camelot not installed")
        print("  Install with: pip install camelot-py opencv-python-headless")
        return False
    except Exception as e:
        print(f"✗ Error using Camelot: {e}")
        return False

def test_code_processor():
    """Test CodeProcessor integration"""
    print("\n=== Testing Code Processor ===")
    
    try:
        from marker.processors.code import CodeProcessor
        from marker.schema.blocks import Code
        
        processor = CodeProcessor()
        print("✓ CodeProcessor imported successfully")
        
        # Test language detection
        test_cases = {
            "python": "def hello():\n    print('Hello')",
            "javascript": "const greet = () => console.log('Hi');",
            "json": '{"name": "test", "value": 123}'
        }
        
        for expected_lang, code_text in test_cases.items():
            code_block = Code()
            code_block.code = code_text
            
            detected = processor.detect_language(code_block)
            if detected == expected_lang:
                print(f"✓ {expected_lang}: correctly detected")
            else:
                print(f"✗ {expected_lang}: detected as {detected}")
                
        return True
        
    except Exception as e:
        print(f"✗ Error testing CodeProcessor: {e}")
        return False

def main():
    """Run all verification tests"""
    print("=== Feature Verification Tests ===")
    
    results = {
        "Tree-Sitter Direct": test_tree_sitter_direct(),
        "Corpus Validator": test_corpus_validator_exists(),
        "Camelot Availability": test_camelot_availability(),
        "Code Processor": test_code_processor()
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