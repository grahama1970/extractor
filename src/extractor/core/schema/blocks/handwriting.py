"""
Module: handwriting.py

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


class Handwriting(Block):
    block_type: BlockTypes = BlockTypes.Handwriting
    block_description: str = "A region that contains handwriting."
    html: str | None = None
    replace_output_newlines: bool = True

    def assemble_html(self, document, child_blocks, parent_structure):
        if self.html:
            return self.html
        else:
            return super().assemble_html(document, child_blocks, parent_structure)
