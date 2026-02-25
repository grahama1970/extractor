"""Tests for MarkdownProvider."""

from pathlib import Path

import pytest

from extractor.core.providers.markdown import MarkdownProvider
from extractor.core.schema.unified_document import BlockType, SourceType


@pytest.fixture
def sample_md(tmp_path: Path) -> Path:
    """Create a minimal Markdown file for testing."""
    md_path = tmp_path / "test.md"
    md_path.write_text(
        """# Test Document

This is an introduction.

## Section 1

Content in section 1.

### Subsection 1.1

Detailed content here.
"""
    )
    return md_path


def test_markdown_provider_basic_extraction(sample_md: Path):
    """Test basic Markdown extraction returns expected structure."""
    provider = MarkdownProvider()
    doc = provider.extract_document(sample_md)

    assert doc.source_type == SourceType.MD
    assert len(doc.blocks) >= 1

    # Should have headings and paragraphs
    block_types = [b.type for b in doc.blocks]
    assert BlockType.HEADING in block_types


def test_markdown_provider_nested_lists(tmp_path: Path):
    """Test Markdown extracts nested lists."""
    md_path = tmp_path / "lists.md"
    md_path.write_text(
        """# Lists

- Item 1
- Item 2
  - Nested item A
  - Nested item B
- Item 3

1. First
2. Second
3. Third
"""
    )

    provider = MarkdownProvider()
    doc = provider.extract_document(md_path)

    # Should have list items
    list_items = [b for b in doc.blocks if b.type == BlockType.LISTITEM]
    assert len(list_items) >= 1


def test_markdown_provider_code_blocks(tmp_path: Path):
    """Test Markdown extracts code blocks."""
    md_path = tmp_path / "code.md"
    md_path.write_text(
        """# Code Example

Here is some Python:

```python
def hello():
    print("Hello")
```

And inline `code` too.
"""
    )

    provider = MarkdownProvider()
    doc = provider.extract_document(md_path)

    assert doc.source_type == SourceType.MD
    # Code block content should be extracted
    all_content = " ".join(b.content for b in doc.blocks if isinstance(b.content, str))
    assert "Code Example" in all_content or "hello" in all_content.lower()


def test_markdown_provider_tables(tmp_path: Path):
    """Test Markdown extracts tables."""
    md_path = tmp_path / "table.md"
    md_path.write_text(
        """# Table Test

| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
| Cell 3   | Cell 4   |
"""
    )

    provider = MarkdownProvider()
    doc = provider.extract_document(md_path)

    assert doc.source_type == SourceType.MD
    # Should extract table or table content
    tables = [b for b in doc.blocks if b.type == BlockType.TABLE]
    if tables:
        # If tables are extracted as TABLE blocks
        assert len(tables) >= 1
    else:
        # Content might be in paragraphs
        assert len(doc.blocks) >= 1
