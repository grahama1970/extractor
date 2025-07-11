"""
Module: fix_table_config_imports.py
Description: Fix table config imports to use actual existing constants

External Dependencies:
- None (uses standard library only)

Sample Input:
>>> from marker.core.config.table import TableConfig, PRESET_HIGH_ACCURACY

Expected Output:
>>> from marker.core.config.table import TableConfig, TABLE_HIGH_QUALITY

Example Usage:
>>> python scripts/fix_table_config_imports.py
"""
"""
Module: fix_table_config_imports.py
Description: Configuration management and settings

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

def fix_test_table_config(filepath):
    """Fix test_table_config.py specifically"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Fix the import statement
    content = re.sub(
        r'from marker\.core\.config\.table import \(\s*TableConfig.*?\)',
        '''from marker.core.config.table import (
    TableConfig, 
    CamelotConfig, 
    TableOptimizerConfig, 
    TableQualityEvaluatorConfig, 
    TableMergerConfig,
    OptimizationMetric,
    TABLE_HIGH_QUALITY,
    TABLE_FAST,
    TABLE_BALANCED
)''',
        content,
        flags=re.DOTALL
    )
    
    # Fix test_presets_are_valid
    content = re.sub(
        r'def test_presets_are_valid\(\):.*?assert isinstance\(PRESET_BALANCED, TableConfig\)',
        '''def test_presets_are_valid():
    """Test that the presets are valid TableConfig objects."""
    assert isinstance(TABLE_HIGH_QUALITY, TableConfig)
    assert isinstance(TABLE_FAST, TableConfig)
    assert isinstance(TABLE_BALANCED, TableConfig)''',
        content,
        flags=re.DOTALL
    )
    
    # Fix test_preset_high_accuracy
    content = re.sub(
        r'def test_preset_high_accuracy\(\):.*?preset = None.*?#.*?removed',
        '''def test_preset_high_accuracy():
    """Test that the high accuracy preset has expected values."""
    preset = TABLE_HIGH_QUALITY''',
        content
    )
    
    # Remove table_config_from_dict import if not needed
    content = re.sub(
        r'from marker\.core\.config\.table_parser import parse_table_config, table_config_from_dict',
        'from marker.core.config.table import table_config_from_dict',
        content
    )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    return True

def fix_other_files(filepath):
    """Fix other test files using PRESET_HIGH_ACCURACY"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Fix imports
    content = re.sub(
        r'from marker\.core\.config\.table import TableConfig, PRESET_HIGH_ACCURACY',
        'from marker.core.config.table import TableConfig, TABLE_HIGH_QUALITY',
        content
    )
    
    # Fix usage
    content = re.sub(
        r'None  # PRESET_HIGH_ACCURACY removed\.model_dump\(\)',
        'TABLE_HIGH_QUALITY.model_dump()',
        content
    )
    
    # Also handle just TableConfig import
    content = re.sub(
        r'from marker\.core\.config\.table import TableConfig\s*$',
        'from marker.core.config.table import TableConfig, TABLE_HIGH_QUALITY',
        content,
        flags=re.MULTILINE
    )
    
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    return False

def main():
    """Main function to fix imports in test files"""
    # Fix test_table_config.py specifically
    test_config_path = Path('tests/core/config/test_table_config.py')
    if test_config_path.exists():
        fix_test_table_config(test_config_path)
        print(f"Fixed: {test_config_path}")
    
    # Fix other files
    other_files = [
        'tests/features/test_enhanced_camelot_conversion.py',
        'tests/features/test_enhanced_camelot_processor.py',
        'tests/core/processors/test_table_extraction_only.py'
    ]
    
    for file_path in other_files:
        path = Path(file_path)
        if path.exists() and fix_other_files(path):
            print(f"Fixed: {path}")
    
    return 0

if __name__ == "__main__":
    exit(main())