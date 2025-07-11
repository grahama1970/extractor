"""
Module: pagefooter.py

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


class PageFooter(Block):
    block_type: str = BlockTypes.PageFooter
    block_description: str = "Text that appears at the bottom of a page, like a page number."
    replace_output_newlines: bool = True
    ignore_for_output: bool = True

