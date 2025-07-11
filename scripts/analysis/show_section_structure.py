"""
Module: show_section_structure.py

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

#!/usr/bin/env python3
"""
Show the complete section structure with all fields
"""
import json
import pprint

# Load the hierarchical output
with open("hierarchical_output.json", "r") as f:
    doc = json.load(f)

# Get a section with subsections to show full structure
main_section = doc["sections"][0]  # Section 1: Introduction
subsection = main_section["subsections"][0]  # Section 1.1: Background

print("COMPLETE SECTION STRUCTURE")
print("="*50)
print("\nRoot Section (1. Introduction):")
print("-"*30)
pprint.pprint(main_section, indent=2)

print("\n\nSubsection (1.1 Background):")  
print("-"*30)
pprint.pprint(subsection, indent=2)