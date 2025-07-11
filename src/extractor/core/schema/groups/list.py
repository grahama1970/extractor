"""
Module: list.py

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


class ListGroup(Group):
    block_type: BlockTypes = BlockTypes.ListGroup
    has_continuation: bool = False
    block_description: str = "A group of list items that should be rendered together."

    def assemble_html(self, document, child_blocks, parent_structure):
        template = super().assemble_html(document, child_blocks, parent_structure)

        el_attr = f" block-type='{self.block_type}'"
        if self.has_continuation:
            el_attr += " class='has-continuation'"
        return f"<p{el_attr}><ul>{template}</ul></p>"
