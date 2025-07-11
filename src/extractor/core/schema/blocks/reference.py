"""
Module: reference.py

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


class Reference(Block):
    block_type: BlockTypes = BlockTypes.Reference
    ref: str
    block_description: str = "A reference to this block from another block."

    def assemble_html(self, document, child_blocks, parent_structure=None):
        template = super().assemble_html(document, child_blocks, parent_structure)
        return f"<span id='{self.ref}'>{template}</span>"
