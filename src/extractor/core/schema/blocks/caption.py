"""
Module: caption.py

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


class Caption(Block):
    block_type: BlockTypes = BlockTypes.Caption
    block_description: str = "A text caption that is directly above or below an image or table. Only used for text describing the image or table.  "
    replace_output_newlines: bool = True
    html: str | None = None

    def assemble_html(self, document, child_blocks, parent_structure):
        if self.html:
            return super().handle_html_output(document, child_blocks, parent_structure)

        return super().assemble_html(document, child_blocks, parent_structure)

