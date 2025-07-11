"""
Module: picture.py

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


class PictureGroup(Group):
    block_type: BlockTypes = BlockTypes.PictureGroup
    block_description: str = "A picture along with associated captions."
