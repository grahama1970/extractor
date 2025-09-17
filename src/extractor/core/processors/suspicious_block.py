"""
Suspicious Block Processor - Detect and mark blocks that may need correction

This processor identifies blocks that appear to have issues like:
- Split headers (incomplete sentences)
- Misclassified text/headers
- Table fragments
"""

from typing import List, Dict, Any
from extractor.core.schema.document import Document
from extractor.core.schema.blocks import Block, BlockType
from extractor.core.processors import BaseProcessor
from loguru import logger


class SuspiciousBlockProcessor(BaseProcessor):
    """Detect and mark suspicious blocks for later correction."""

    def __init__(self):
        super().__init__()
        self.suspicious_patterns = [
            # Headers split across blocks
            (
                r"^\d+\.\d+\.?\d*\.?\s+\w+.*\($",
                "incomplete_header",
            ),  # "4.1.5.4. BHT (Branch History"
            (r"^\w+\)$", "header_continuation"),  # "Table)"
            # Sentence fragments
            (r"^[a-z]", "lowercase_start"),  # Starts with lowercase
            (r"^(and|or|but|with|from|to|in|on|at|by)\s", "conjunction_start"),
            # Table issues
            (r"^\|.*\|$", "possible_table_row"),
            (r"^[\w\s]+\|[\w\s]+\|", "pipe_separated"),
            # Other patterns
            (r"^\.{3}", "ellipsis_start"),
            (r"\.\.\.$", "ellipsis_end"),
            (r"^,\s*", "comma_start"),
        ]

    def __call__(self, document: Document) -> Document:
        """Process document to detect suspicious blocks."""

        suspicious_count = 0

        for page in document.pages:
            blocks = list(page.children)

            for i, block in enumerate(blocks):
                if not hasattr(block, "text") or not block.text:
                    continue

                # Check each pattern
                issues = []
                text = block.text.strip()

                # Pattern-based detection
                import re

                for pattern, issue_type in self.suspicious_patterns:
                    if re.search(pattern, text):
                        issues.append(issue_type)

                # Context-based detection
                if i > 0:
                    prev_block = blocks[i - 1]
                    if hasattr(prev_block, "text") and prev_block.text:
                        # Check for split sentences
                        if prev_block.text.rstrip().endswith("(") and not text.startswith("("):
                            issues.append("possible_split_parentheses")

                        # Check for continuation
                        if not prev_block.text.rstrip().endswith(".") and text[0].islower():
                            issues.append("possible_continuation")

                if i < len(blocks) - 1:
                    next_block = blocks[i + 1]
                    if hasattr(next_block, "text") and next_block.text:
                        # Check for split headers
                        if text.rstrip().endswith("(") and next_block.text.strip().endswith(")"):
                            issues.append("split_header_start")

                # Length-based heuristics
                if len(text) < 20 and block.block_type == BlockType.TEXT:
                    # Short text blocks are often fragments
                    if not text.endswith("."):
                        issues.append("short_fragment")

                # Mark block as suspicious if issues found
                if issues:
                    # Initialize validation_metadata if needed
                    if (
                        not hasattr(block, "validation_metadata")
                        or block.validation_metadata is None
                    ):
                        block.validation_metadata = {}

                    block.validation_metadata["suspicious"] = True
                    block.validation_metadata["suspicious_issues"] = issues
                    suspicious_count += 1

                    logger.debug(
                        f"Marked block {i} as suspicious: {issues[:2]}... Text: '{text[:40]}...'"
                    )

        logger.info(f"SuspiciousBlockProcessor: Marked {suspicious_count} blocks as suspicious")

        return document


# Usage examples
async def working_usage():
    """Demonstrate suspicious block detection."""
    from extractor.core.schema.document import Document
    from extractor.core.schema.page import Page
    from extractor.core.schema.blocks import Block, BlockType
    from extractor.core.schema.polygon import PolygonBox

    # Create test document with suspicious blocks
    doc = Document()
    page = Page(page_id=0, bbox=PolygonBox.from_bbox([0, 0, 100, 100]))

    # Add test blocks
    blocks = [
        Block(
            id="1",
            block_type=BlockType.TEXT,
            text="4.1.5.4. BHT (Branch History",
            polygon=PolygonBox.from_bbox([10, 10, 90, 20]),
        ),
        Block(
            id="2",
            block_type=BlockType.TEXT,
            text="Table) submodule",
            polygon=PolygonBox.from_bbox([10, 20, 90, 30]),
        ),
        Block(
            id="3",
            block_type=BlockType.TEXT,
            text="BHT is implemented as a memory.",
            polygon=PolygonBox.from_bbox([10, 30, 90, 40]),
        ),
    ]

    for block in blocks:
        page.add_child(block)
    doc.add_child(page)

    # Process
    processor = SuspiciousBlockProcessor()
    processed_doc = processor(doc)

    # Check results
    print("Suspicious blocks found:")
    for page in processed_doc.pages:
        for i, block in enumerate(page.children):
            if hasattr(block, "validation_metadata") and block.validation_metadata:
                if block.validation_metadata.get("suspicious"):
                    print(f"  Block {i}: {block.text[:40]}...")
                    print(f"    Issues: {block.validation_metadata.get('suspicious_issues')}")

    return True


async def debug_function():
    """Test pattern matching and edge cases."""
    import re

    processor = SuspiciousBlockProcessor()

    test_texts = [
        "4.1.5.4. BHT (Branch History",  # incomplete_header
        "Table) submodule",  # header_continuation
        "and continues here",  # conjunction_start
        "table continues",  # lowercase_start
        "|Cell1|Cell2|Cell3|",  # possible_table_row
        "Signal|IO|Description",  # pipe_separated
        "... continued from above",  # ellipsis_start
        "This text trails off...",  # ellipsis_end
        ", which is important",  # comma_start
    ]

    print("Pattern matching tests:")
    for text in test_texts:
        issues = []
        for pattern, issue_type in processor.suspicious_patterns:
            if re.search(pattern, text):
                issues.append(issue_type)

        if issues:
            print(f"'{text}' -> {issues}")

    return True


if __name__ == "__main__":
    """
    AGENT INSTRUCTIONS:
    - DEFAULT: Runs working_usage() - stable example that works
    - DEBUG: Run with 'debug' argument to test pattern matching
    - DO NOT create external test files - use debug_function() instead!
    """
    import asyncio
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "working"

    if mode == "debug":
        print("Running debug mode...")
        asyncio.run(debug_function())
    else:
        print("Running working usage mode...")
        asyncio.run(working_usage())
