"""
Module: schema.py

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

from typing import TypedDict, List, Optional, Dict


class BlockScores(TypedDict):
    score: float
    specific_scores: Dict[str, float | List[float]]
