#!/usr/bin/env python3
"""Check all tree-sitter language support"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from marker.services.utils.tree_sitter_utils import LANGUAGE_MAPPINGS, get_supported_language

# Get unique language names from the mappings
unique_languages = set(LANGUAGE_MAPPINGS.values())

supported_count = 0
unsupported_languages = []

print("=== Tree-Sitter Language Support Check ===")
print(f"Total languages defined: {len(unique_languages)}")
print("\nChecking each language:")

for lang in sorted(unique_languages):
    supported = get_supported_language(lang)
    if supported:
        print(f"✓ {lang}")
        supported_count += 1
    else:
        print(f"✗ {lang}")
        unsupported_languages.append(lang)

print(f"\nSummary:")
print(f"Supported: {supported_count}/{len(unique_languages)}")
print(f"Unsupported: {len(unsupported_languages)}")

if unsupported_languages:
    print("\nUnsupported languages:")
    for lang in unsupported_languages:
        print(f"  - {lang}")