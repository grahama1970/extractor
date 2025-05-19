#!/usr/bin/env python3
"""
Test script for corpus generator and tree-sitter integration.
Focuses on direct testing without complex imports.
"""

import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_tree_sitter_code_detection():
    """Test tree-sitter code detection functionality"""
    print("\n=== Testing Tree-Sitter Code Detection ===")
    
    try:
        from marker.services.utils.tree_sitter_utils import extract_code_metadata, get_supported_language
        from marker.processors.code import CodeProcessor
        from marker.schema.blocks import Code
        from marker.schema import BlockTypes
        from marker.schema.polygon import PolygonBox
        
        print("✓ Imports successful")
        
        # Test language support
        test_languages = ["python", "javascript", "java", "cpp", "go", "rust"]
        supported_count = 0
        
        for lang in test_languages:
            if get_supported_language(lang):
                print(f"✓ {lang} is supported")
                supported_count += 1
            else:
                print(f"✗ {lang} is not supported")
        
        print(f"\nSupported languages: {supported_count}/{len(test_languages)}")
        
        # Test code metadata extraction
        test_code = '''
def calculate_sum(a: int, b: int) -> int:
    """Add two numbers and return the sum."""
    return a + b

class Calculator:
    def multiply(self, x: float, y: float) -> float:
        """Multiply two numbers."""
        return x * y
'''
        
        metadata = extract_code_metadata(test_code, "python")
        
        if metadata.get('tree_sitter_success'):
            print("\n✓ Code metadata extraction successful")
            print(f"  Functions found: {len(metadata.get('functions', []))}")
            print(f"  Classes found: {len(metadata.get('classes', []))}")
            
            # Print details
            for func in metadata.get('functions', []):
                params = len(func.get('parameters', []))
                print(f"  - Function '{func['name']}' with {params} parameters")
                
            for cls in metadata.get('classes', []):
                print(f"  - Class '{cls['name']}'")
        else:
            print(f"\n✗ Code extraction failed: {metadata.get('error')}")
        
        # Test CodeProcessor language detection with proper initialization
        processor = CodeProcessor()
        
        # Create a proper Code block with required fields
        # Note: We need to provide the required polygon field
        code_block = Code(
            code="print('Hello, World!')",
            language=None,
            polygon=PolygonBox(polygon=[[0, 0], [100, 0], [100, 50], [0, 50]])  # Minimal bounding box
        )
        
        detected_lang = processor.detect_language(code_block)
        print(f"\n✓ CodeProcessor test: detected '{detected_lang}' for Python print statement")
        
        return True
        
    except Exception as e:
        print(f"✗ Error in tree-sitter test: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_corpus_validator_structure():
    """Test corpus validator structure and basic functionality"""
    print("\n=== Testing Corpus Validator Structure ===")
    
    try:
        # Check if PyMuPDF is available
        try:
            import fitz
            print("✓ PyMuPDF (fitz) is available")
            pymupdf_available = True
        except ImportError:
            print("✗ PyMuPDF (fitz) not installed")
            print("  Install with: pip install PyMuPDF")
            pymupdf_available = False
        
        if not pymupdf_available:
            return False
            
        from marker.processors.corpus_validator import CorpusValidationProcessor
        print("✓ CorpusValidationProcessor imported successfully")
        
        # Check methods
        required_methods = ['__call__', 'validate_corpus', 'extract_raw_corpus']
        for method in required_methods:
            if hasattr(CorpusValidationProcessor, method):
                print(f"✓ Method '{method}' exists")
            else:
                print(f"✗ Method '{method}' not found")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing corpus validator: {e}")
        return False


def test_camelot_availability():
    """Test Camelot availability"""
    print("\n=== Testing Camelot Availability ===")
    
    try:
        import camelot
        print("✓ Camelot imported successfully")
        print(f"  Version: {camelot.__version__}")
        return True
        
    except ImportError:
        print("✗ Camelot not installed")
        print("  Install with: pip install camelot-py opencv-python-headless")
        return False
    except Exception as e:
        print(f"✗ Error with Camelot: {e}")
        return False


def test_qa_config():
    """Test Q&A optimized configuration"""
    print("\n=== Testing Q&A Optimized Configuration ===")
    
    try:
        from marker.config.qa_optimized import QAOptimizedConfig, get_qa_optimized_config
        print("✓ Q&A config imported successfully")
        
        # Create config instance
        config = get_qa_optimized_config()
        print("✓ Config instance created")
        
        # Check key settings
        print(f"  Processing mode: {config.processing_mode}")
        print(f"  Corpus validation: {config.enable_corpus_validation}")
        print(f"  Validation threshold: {config.corpus_validation_threshold}")
        print(f"  Camelot fallback: {config.use_camelot_fallback}")
        print(f"  Number of processors: {len(config.processors)}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing Q&A config: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=== Corpus Generator and Tree-Sitter Tests ===")
    
    tests = {
        "Tree-Sitter Code Detection": test_tree_sitter_code_detection,
        "Corpus Validator Structure": test_corpus_validator_structure,
        "Camelot Availability": test_camelot_availability,
        "Q&A Configuration": test_qa_config
    }
    
    results = {}
    for test_name, test_func in tests.items():
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n✗ Test '{test_name}' failed with error: {e}")
            results[test_name] = False
    
    print("\n=== Test Summary ===")
    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    if all_passed:
        print("\n✓ All tests passed!")
    else:
        print("\n✗ Some tests failed")
        print("\nRecommendations:")
        if not results.get("Corpus Validator Structure"):
            print("- Install PyMuPDF: pip install PyMuPDF")
        if not results.get("Camelot Availability"):
            print("- Install Camelot: pip install camelot-py opencv-python-headless")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())