"""
Module: utils.py
Description: Utility functions and helpers for utils

External Dependencies:
- None (uses only standard library)

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

def alphanum_ratio(text):
    text = text.replace(" ", "")
    text = text.replace("\n", "")
    alphanumeric_count = sum([1 for c in text if c.isalnum()])

    if len(text) == 0:
        return 1

    ratio = alphanumeric_count / len(text)
    return ratio
