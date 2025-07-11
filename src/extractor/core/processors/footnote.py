"""
Module: footnote.py

External Dependencies:
- marker: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

import re

from extractor.core.processors import BaseProcessor
from extractor.core.schema import BlockTypes
from extractor.core.schema.document import Document
from extractor.core.schema.groups import PageGroup


class FootnoteProcessor(BaseProcessor):
    """
    A processor for pushing footnotes to the bottom, and relabeling mislabeled text blocks.
    """
    block_types = (BlockTypes.Footnote,)

    def __call__(self, document: Document):
        for page in document.pages:
            self.push_footnotes_to_bottom(page, document)
            self.assign_superscripts(page, document)

    def push_footnotes_to_bottom(self, page: PageGroup, document: Document):
        footnote_blocks = page.contained_blocks(document, self.block_types)

        # Push footnotes to the bottom
        for block in footnote_blocks:
            # Check if it is top-level
            if block.id in page.structure:
                # Move to bottom if it is
                page.structure.remove(block.id)
                page.add_structure(block)

    def assign_superscripts(self, page: PageGroup, document: Document):
        footnote_blocks = page.contained_blocks(document, self.block_types)

        for block in footnote_blocks:
            for span in block.contained_blocks(document, (BlockTypes.Span,)):
                if re.match(r"^[0-9\W]+", span.text):
                    span.has_superscript = True
                break
