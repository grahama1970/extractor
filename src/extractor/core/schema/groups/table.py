"""
Module: table.py

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


class TableGroup(Group):
    block_type: BlockTypes = BlockTypes.TableGroup
    block_description: str = "A table along with associated captions."
