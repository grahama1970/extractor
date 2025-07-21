#!/usr/bin/env python3
"""
Diagnostic script to troubleshoot extractor imports in other projects.

Run this to identify what's missing or misconfigured.
"""

import sys
import os
from pathlib import Path


def diagnose_imports():
    """Check if all required imports work."""
    
    print("EXTRACTOR IMPORT DIAGNOSTICS")
    print("=" * 60)
    
    # Check Python path
    print("\n1. PYTHON PATH:")
    print("-" * 40)
    for i, path in enumerate(sys.path):
        print(f"  [{i}] {path}")
    
    # Check current directory
    print(f"\n2. CURRENT DIRECTORY: {os.getcwd()}")
    
    # Check for src directory
    src_path = Path("src")
    if src_path.exists():
        print(f"   ✓ src/ directory found")
    else:
        print(f"   ✗ src/ directory NOT found")
        print(f"     Searching for extractor in parent directories...")
        
        # Search for extractor module
        current = Path.cwd()
        found = False
        for parent in [current] + list(current.parents):
            potential_path = parent / "src" / "extractor"
            if potential_path.exists():
                print(f"   ✓ Found extractor at: {potential_path}")
                found = True
                break
        
        if not found:
            print(f"   ✗ Could not find extractor module")
    
    # Test imports
    print("\n3. TESTING IMPORTS:")
    print("-" * 40)
    
    imports_to_test = [
        ("extractor", "Base module"),
        ("extractor.core", "Core module"),
        ("extractor.core.convert", "Convert module"),
        ("extractor.core.converters.pdf", "PDF converter"),
        ("extractor.core.renderers.json", "JSON renderer"),
        ("extractor.core.models", "Models"),
        ("extractor.core.schema", "Schema"),
    ]
    
    successful_imports = []
    failed_imports = []
    
    for module_name, description in imports_to_test:
        try:
            __import__(module_name)
            print(f"   ✓ {description:<20} ({module_name})")
            successful_imports.append(module_name)
        except ImportError as e:
            print(f"   ✗ {description:<20} ({module_name})")
            print(f"      Error: {e}")
            failed_imports.append((module_name, str(e)))
    
    # Test key functions
    print("\n4. TESTING KEY FUNCTIONS:")
    print("-" * 40)
    
    if "extractor.core.convert" in successful_imports:
        try:
            from extractor.core.convert import convert_pdf_to_json
            print("   ✓ convert_pdf_to_json function available")
        except ImportError as e:
            print(f"   ✗ convert_pdf_to_json function not available: {e}")
    
    # Check dependencies
    print("\n5. CHECKING DEPENDENCIES:")
    print("-" * 40)
    
    dependencies = [
        ("pydantic", "Data validation"),
        ("pymupdf", "PDF processing", "fitz"),
        ("PIL", "Image processing"),
        ("torch", "Deep learning"),
        ("transformers", "NLP models"),
    ]
    
    for dep_info in dependencies:
        module = dep_info[0]
        desc = dep_info[1]
        import_name = dep_info[2] if len(dep_info) > 2 else module
        
        try:
            __import__(import_name)
            print(f"   ✓ {desc:<20} ({module})")
        except ImportError:
            print(f"   ✗ {desc:<20} ({module}) - NOT INSTALLED")
    
    # Provide solutions
    print("\n6. RECOMMENDED FIXES:")
    print("-" * 40)
    
    if failed_imports:
        print("\nFor import errors:")
        print("1. Add extractor src to PYTHONPATH:")
        print(f"   export PYTHONPATH={Path.cwd() / 'src'}:$PYTHONPATH")
        print("\n2. Or add to your Python script:")
        print("   import sys")
        print(f"   sys.path.insert(0, '{Path.cwd() / 'src'}')")
        
    print("\nFor missing dependencies:")
    print("   pip install pymupdf pydantic pillow torch transformers")
    print("   # or")
    print("   uv add pymupdf pydantic pillow torch transformers")
    
    # Create a test script
    print("\n7. CREATING TEST SCRIPT:")
    print("-" * 40)
    
    test_script = '''#!/usr/bin/env python3
"""Auto-generated test script for extractor imports."""

import sys
from pathlib import Path

# Add this to your script to fix import issues
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Now try the import
try:
    from extractor.core.convert import convert_pdf_to_json
    print("✓ Import successful!")
    
    # Test with a PDF if you have one
    # result = convert_pdf_to_json("test.pdf")
    # print(f"✓ Conversion successful! Got {len(result.get('children', []))} pages")
    
except ImportError as e:
    print(f"✗ Import failed: {e}")
    print("\\nMake sure:")
    print("1. You're in the right directory")
    print("2. The extractor module is in the src/ directory")
    print("3. All dependencies are installed")
'''
    
    with open("test_extractor_import.py", "w") as f:
        f.write(test_script)
    
    print("✓ Created test_extractor_import.py")
    print("  Run it to test your setup: python test_extractor_import.py")


if __name__ == "__main__":
    diagnose_imports()