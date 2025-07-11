"""
Module: pageheader.py

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
from extractor.core.schema.blocks import Block


class PageHeader(Block):
    block_type: BlockTypes = BlockTypes.PageHeader
    block_description: str = "Text that appears at the top of a page, like a page title."
    replace_output_newlines: bool = True
    ignore_for_output: bool = True

