"""
Module: toc.py

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
from extractor.core.schema.blocks.basetable import BaseTable


class TableOfContents(BaseTable):
    block_type: str = BlockTypes.TableOfContents
    block_description: str = "A table of contents."
