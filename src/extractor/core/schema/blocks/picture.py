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
from extractor.core.schema.blocks import Block


class Picture(Block):
    block_type: BlockTypes = BlockTypes.Picture
    description: str | None = None
    block_description: str = "An image block that represents a picture."

    def assemble_html(self, document, child_blocks, parent_structure):
        child_ref_blocks = [block for block in child_blocks if block.id.block_type == BlockTypes.Reference]
        html = super().assemble_html(document, child_ref_blocks, parent_structure)

        if self.description:
            return html + f"<p role='img' data-original-image-id='{self.id}'>Image {self.id} description: {self.description}</p>"
        return html
