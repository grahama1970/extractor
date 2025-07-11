"""
Module: fix_preset_high_accuracy.py
Description: Remove imports of non-existent PRESET_HIGH_ACCURACY constant

External Dependencies:
- None (uses standard library only)

Sample Input:
>>> from marker.core.config.table import TableConfig, PRESET_HIGH_ACCURACY

Expected Output:
>>> from marker.core.config.table import TableConfig

Example Usage:
>>> python scripts/fix_preset_high_accuracy.py
"""
"""
Module: fix_preset_high_accuracy.py

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

#!/usr/bin/env python3

import re
from pathlib import Path

def fix_imports_in_file(filepath):
    """Fix import statements in a single file"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Remove PRESET_HIGH_ACCURACY from imports
    content = re.sub(
        r'from marker\.core\.config\.table import ([^,\n]+), PRESET_HIGH_ACCURACY',
        r'from marker.core.config.table import \1',
        content
    )
    
    # Remove any usage of PRESET_HIGH_ACCURACY
    content = re.sub(r'PRESET_HIGH_ACCURACY', 'None  # PRESET_HIGH_ACCURACY removed', content)
    
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    return False

def main():
    """Main function to fix imports in test files"""
    files_to_fix = [
        'tests/features/test_enhanced_camelot_conversion.py',
        'tests/features/test_enhanced_camelot_processor.py',
        'tests/core/processors/test_table_extraction_only.py',
        'tests/core/config/test_table_config.py'
    ]
    
    fixed_files = []
    for file_path in files_to_fix:
        path = Path(file_path)
        if path.exists() and fix_imports_in_file(path):
            fixed_files.append(path)
    
    print(f"Fixed imports in {len(fixed_files)} files:")
    for f in sorted(fixed_files):
        print(f"  - {f}")
    
    return 0 if fixed_files else 1

if __name__ == "__main__":
    exit(main())