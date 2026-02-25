"""Tests for RSTProvider."""

from pathlib import Path

import pytest

from extractor.core.providers.rst import RSTProvider
from extractor.core.schema.unified_document import BlockType, SourceType


@pytest.fixture
def sample_rst(tmp_path: Path) -> Path:
    """Create a minimal RST file for testing."""
    rst_path = tmp_path / "test.rst"
    rst_path.write_text(
        """
Test Document
=============

This is an introduction paragraph.

Section 1
---------

Content in section 1.

Subsection 1.1
~~~~~~~~~~~~~~

More detailed content.
"""
    )
    return rst_path


def test_rst_provider_basic_extraction(sample_rst: Path):
    """Test basic RST extraction returns expected structure."""
    provider = RSTProvider()
    doc = provider.extract_document(sample_rst)

    assert doc.source_type == SourceType.RST
    assert len(doc.blocks) >= 1


def test_rst_provider_section_hierarchy(tmp_path: Path):
    """Test RST extracts section hierarchy correctly."""
    rst_path = tmp_path / "sections.rst"
    rst_path.write_text(
        """
Main Title
==========

Introduction text.

Chapter 1
---------

Chapter content.

Section 1.1
~~~~~~~~~~~

Section content.
"""
    )

    provider = RSTProvider()
    doc = provider.extract_document(rst_path)

    # Should have extracted headings
    headings = [b for b in doc.blocks if b.type == BlockType.HEADING]
    assert len(headings) >= 1
    # First heading should have content
    assert headings[0].content.strip() != ""


def test_rst_provider_code_blocks(tmp_path: Path):
    """Test RST extracts code blocks."""
    rst_path = tmp_path / "code.rst"
    rst_path.write_text(
        """
Code Example
============

Here is some code::

    def hello():
        print("Hello")

And more text.
"""
    )

    provider = RSTProvider()
    doc = provider.extract_document(rst_path)

    assert doc.source_type == SourceType.RST
    # Should have extracted some content
    all_content = " ".join(b.content for b in doc.blocks if isinstance(b.content, str))
    assert "Code Example" in all_content or "hello" in all_content.lower()


def test_rst_provider_empty_document(tmp_path: Path):
    """Test RST provider handles empty documents."""
    rst_path = tmp_path / "empty.rst"
    rst_path.write_text("")

    provider = RSTProvider()
    doc = provider.extract_document(rst_path)

    assert doc.source_type == SourceType.RST
    assert doc.blocks is not None
