"""
Module: complexregion.py

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


class ComplexRegion(Block):
    block_type: BlockTypes = BlockTypes.ComplexRegion
    html: str | None = None
    block_description: str = "A complex region that can consist of multiple different types of blocks mixed with images. This block is chosen when it is difficult to categorize the region as a single block type."

    def assemble_html(self, document, child_blocks, parent_structure):
        if self.html:
            child_ref_blocks = [block for block in child_blocks if block.id.block_type == BlockTypes.Reference]
            html = super().assemble_html(document, child_ref_blocks, parent_structure)
            return html + self.html
        else:
            template = super().assemble_html(document, child_blocks, parent_structure)
            return f"<p>{template}</p>"
