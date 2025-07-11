"""
Module: fix_test_imports.py
Description: Fix import paths in test files after marker package restructuring

External Dependencies:
- None (uses standard library only)

Sample Input:
>>> from marker.config import ConfigParser
>>> from marker.models import create_model_dict

Expected Output:
>>> from marker.core.config import ConfigParser
>>> from marker.core.models import create_model_dict

Example Usage:
>>> python scripts/fix_test_imports.py
"""
"""
Module: fix_test_imports.py
Description: Test suite for fix_imports functionality

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if src_path.exists() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))



#!/usr/bin/env python3

import os
import re
from pathlib import Path

def fix_imports_in_file(filepath):
    """Fix import statements in a single file"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Dictionary of import replacements
    replacements = {
        # Direct module replacements
        r'from marker\.config(?![.\w])': 'from marker.core.config',
        r'from marker\.models(?![.\w])': 'from marker.core.models',
        r'from marker\.util(?![.\w])': 'from marker.core.util',
        r'from marker\.utils(?![.\w])': 'from marker.core.utils',
        r'from marker\.arangodb(?![.\w])': 'from marker.core.arangodb',
        r'from marker\.settings(?![.\w])': 'from marker.core.settings',
        r'from marker\.output(?![.\w])': 'from marker.core.output',
        r'from marker\.logger(?![.\w])': 'from marker.core.logger',
        
        # Submodule imports
        r'from marker\.config\.': 'from marker.core.config.',
        r'from marker\.models\.': 'from marker.core.models.',
        r'from marker\.util\.': 'from marker.core.util.',
        r'from marker\.utils\.': 'from marker.core.utils.',
        
        # Import statement replacements
        r'import marker\.config(?![.\w])': 'import marker.core.config',
        r'import marker\.models(?![.\w])': 'import marker.core.models',
        r'import marker\.util(?![.\w])': 'import marker.core.util',
        r'import marker\.utils(?![.\w])': 'import marker.core.utils',
        r'import marker\.settings(?![.\w])': 'import marker.core.settings',
        
        # Specific module replacements
        r'from marker\.core\.processors\.hierarchy_builder': 'from marker.core.processors.enhanced.hierarchy_builder',
        r'from marker\.processors\.hierarchy_builder': 'from marker.core.processors.enhanced.hierarchy_builder',
    }
    
    original_content = content
    for pattern, replacement in replacements.items():
        content = re.sub(pattern, replacement, content)
    
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    return False

def main():
    """Main function to fix imports in all test files"""
    test_dir = Path('tests')
    fixed_files = []
    
    for py_file in test_dir.rglob('*.py'):
        if fix_imports_in_file(py_file):
            fixed_files.append(py_file)
    
    print(f"Fixed imports in {len(fixed_files)} files:")
    for f in sorted(fixed_files):
        print(f"  - {f}")
    
    return 0 if fixed_files else 1

if __name__ == "__main__":
    exit(main())