"""
Module: __init__.py
Description: Package initialization and exports

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

from typing import List

from benchmarks.overall.scorers.schema import BlockScores


class BaseScorer:
    def __init__(self):
        pass

    def __call__(self, sample, gt_markdown: List[str], method_markdown: str) -> BlockScores:
        raise NotImplementedError()