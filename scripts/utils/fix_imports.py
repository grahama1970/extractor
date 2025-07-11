"""
Module: fix_imports.py

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

#!/usr/bin/env python3
"""Fix imports after restructuring marker project."""

import os
import re
from pathlib import Path

def fix_imports_in_file(filepath):
    """Fix imports in a single Python file."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Fix imports that need to add .core
    replacements = [
        # From marker.X to marker.core.X (where X is not cli, core, or mcp)
        (r'from marker\.(?!(core|cli|mcp)\.)([a-zA-Z_]+)', r'from marker.core.\2'),
        (r'import marker\.(?!(core|cli|mcp)\.)([a-zA-Z_]+)', r'import marker.core.\2'),
        
        # Specific module movements
        (r'from marker\.renderers', r'from marker.core.renderers'),
        (r'from marker\.schema', r'from marker.core.schema'),
        (r'from marker\.settings', r'from marker.core.settings'),
        (r'from marker\.models', r'from marker.core.models'),
        (r'from marker\.logger', r'from marker.core.logger'),
        (r'from marker\.util', r'from marker.core.util'),
        (r'from marker\.output', r'from marker.core.output'),
        (r'from marker\.builders', r'from marker.core.builders'),
        (r'from marker\.converters', r'from marker.core.converters'),
        (r'from marker\.processors', r'from marker.core.processors'),
        (r'from marker\.providers', r'from marker.core.providers'),
        (r'from marker\.utils', r'from marker.core.utils'),
        (r'from marker\.services', r'from marker.core.services'),
        (r'from marker\.config', r'from marker.core.config'),
        (r'from marker\.scripts', r'from marker.core.scripts'),
        (r'from marker\.arangodb', r'from marker.core.arangodb'),
        (r'from marker\.llm_call', r'from marker.core.llm_call'),
        
        # Import statements
        (r'import marker\.renderers', r'import marker.core.renderers'),
        (r'import marker\.schema', r'import marker.core.schema'),
        (r'import marker\.settings', r'import marker.core.settings'),
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    return False

def main():
    """Fix all imports in the marker project."""
    fixed_files = []
    
    # Find all Python files
    for root, dirs, files in os.walk('src/marker'):
        # Skip __pycache__ directories
        if '__pycache__' in root:
            continue
            
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                if fix_imports_in_file(filepath):
                    fixed_files.append(filepath)
                    print(f"Fixed: {filepath}")
    
    print(f"\nTotal files fixed: {len(fixed_files)}")

if __name__ == "__main__":
    main()
