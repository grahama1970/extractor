#!/usr/bin/env python3
"""
Script to fix missing dependencies for Surya models in extractor
"""

import subprocess
import sys

def run_command(cmd):
    """Run a command and return success/failure"""
    try:
        print(f"Running: {cmd}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Success")
            return True
        else:
            print(f"❌ Failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("🔧 Fixing Surya dependencies for extractor")
    print("=" * 50)
    
    # Change to extractor directory
    import os
    os.chdir("/home/graham/workspace/experiments/extractor")
    
    # Dependencies to install
    deps = [
        "opencv-python",  # cv2
        "opencv-python-headless",  # Alternative cv2 for servers
        "pymupdf",  # For PDF processing
        "pytesseract",  # OCR support
        "pdf2image",  # PDF to image conversion
        "poppler-utils",  # PDF utilities
    ]
    
    print("\n📦 Installing missing dependencies...")
    
    for dep in deps:
        print(f"\nInstalling {dep}...")
        if run_command(f"uv add {dep}"):
            print(f"   ✅ {dep} installed")
        else:
            print(f"   ❌ Failed to install {dep}")
    
    print("\n🔍 Verifying imports...")
    
    # Test imports
    test_imports = [
        ("cv2", "import cv2"),
        ("fitz", "import fitz"),  # PyMuPDF
        ("surya", "from surya.layout import LayoutPredictor"),
        ("extractor models", "from extractor.core.models import create_model_dict"),
    ]
    
    for name, import_stmt in test_imports:
        try:
            exec(import_stmt)
            print(f"✅ {name} imports successfully")
        except ImportError as e:
            print(f"❌ {name} import failed: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Dependency fix complete")
    print("\nNext steps:")
    print("1. Run the extractor usage functions again")
    print("2. Verify Surya models load properly")
    print("3. Test PDF extraction with real data")

if __name__ == "__main__":
    main()