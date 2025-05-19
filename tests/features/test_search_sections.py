#!/usr/bin/env python3
"""
Test script to find documents with sections.
"""

import os
import json
from pathlib import Path


def find_sections_in_json(file_path):
    """Check if a JSON file has sections."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Count sections recursively
        section_count = 0
        
        def count_sections(node):
            nonlocal section_count
            if isinstance(node, dict):
                if node.get('block_type') == 'SectionHeader':
                    section_count += 1
                
                # Check children
                if 'children' in node and isinstance(node['children'], list):
                    for child in node['children']:
                        count_sections(child)
                
                # Check pages
                if 'pages' in node and isinstance(node['pages'], list):
                    for page in node['pages']:
                        count_sections(page)
        
        count_sections(data)
        return section_count
    
    except Exception as e:
        return 0


def main():
    # Look for existing JSON files
    json_files = list(Path('.').glob('*.json'))
    
    for json_file in json_files:
        sections = find_sections_in_json(json_file)
        if sections > 0:
            print(f"{json_file}: {sections} sections")
    
    # Also check existing output files
    output_files = ['regular_output.json', 'merged_output.json', 'test_with_summaries.json']
    for output_file in output_files:
        if os.path.exists(output_file):
            sections = find_sections_in_json(output_file)
            print(f"{output_file}: {sections} sections")


if __name__ == "__main__":
    main()