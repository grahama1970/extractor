#!/usr/bin/env python3
"""Debug import issues."""

import sys
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")

# Test basic imports
try:
    import regex
    print(f"✓ regex imported: {regex.__version__}")
except Exception as e:
    print(f"✗ regex import failed: {e}")

try:
    import cffi
    print(f"✓ cffi imported: {cffi.__version__}")
except Exception as e:
    print(f"✗ cffi import failed: {e}")

try:
    from bs4 import BeautifulSoup
    print(f"✓ BeautifulSoup imported")
except Exception as e:
    print(f"✗ BeautifulSoup import failed: {e}")

# Try importing extractor without all the dependencies
try:
    sys.path.insert(0, '/home/graham/workspace/experiments/extractor/src')
    # Just try to import the basic module structure
    import extractor.core.renderers.json as json_renderer
    print("✓ JSON renderer imported")
except SyntaxError as e:
    print(f"✗ Syntax error: {e}")
    print(f"  File: {e.filename}")
    print(f"  Line: {e.lineno}")
    print(f"  Text: {e.text}")
except Exception as e:
    print(f"✗ Import error: {type(e).__name__}: {e}")