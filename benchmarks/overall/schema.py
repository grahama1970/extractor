"""
Module: schema.py

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

from typing import TypedDict, List, Dict

from benchmarks.overall.scorers.schema import BlockScores

AVG_TYPE = Dict[str, Dict[str, Dict[str, List[float]]]]

class FullResult(TypedDict):
    scores: Dict[int, Dict[str, Dict[str, BlockScores]]]
    averages_by_type: AVG_TYPE
    averages_by_block_type: AVG_TYPE
    average_times: Dict[str, List[float]]
    markdown: Dict[int, Dict[str, str]]
