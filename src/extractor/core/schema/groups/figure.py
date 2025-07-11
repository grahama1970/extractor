"""
Module: figure.py

External Dependencies:
- marker: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

from extractor.core.schema import BlockTypes
from extractor.core.schema.groups.base import Group


class FigureGroup(Group):
    block_type: BlockTypes = BlockTypes.FigureGroup
    block_description: str = "A group that contains a figure and associated captions."
