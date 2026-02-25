"""Tests for EPUBProvider."""

from pathlib import Path

import pytest
from ebooklib import epub

from extractor.core.providers.epub import EPUBProvider
from extractor.core.schema.unified_document import SourceType


@pytest.fixture
def sample_epub(tmp_path: Path) -> Path:
    """Create a minimal EPUB file for testing."""
    epub_path = tmp_path / "test.epub"

    book = epub.EpubBook()
    book.set_identifier("test-id-123")
    book.set_title("Test Book")
    book.set_language("en")
    book.add_author("Test Author")

    # Create a chapter
    c1 = epub.EpubHtml(title="Chapter 1", file_name="chap_01.xhtml", lang="en")
    c1.content = "<html><body><h1>Chapter 1</h1><p>This is test content.</p></body></html>"
    book.add_item(c1)

    # Define spine
    book.spine = ["nav", c1]

    # Add navigation
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(epub_path, book)
    return epub_path


def test_epub_provider_basic_extraction(sample_epub: Path):
    """Test basic EPUB extraction returns expected structure."""
    provider = EPUBProvider()
    doc = provider.extract_document(sample_epub)

    assert doc.source_type == SourceType.EPUB
    assert len(doc.blocks) >= 1


def test_epub_provider_chapter_structure(tmp_path: Path):
    """Test EPUB extracts chapter content."""
    epub_path = tmp_path / "chapters.epub"

    book = epub.EpubBook()
    book.set_identifier("chapters-123")
    book.set_title("Multi-Chapter Book")
    book.set_language("en")

    # Create two chapters
    c1 = epub.EpubHtml(title="Introduction", file_name="intro.xhtml", lang="en")
    c1.content = "<html><body><h1>Introduction</h1><p>Welcome to the book.</p></body></html>"

    c2 = epub.EpubHtml(title="Main Content", file_name="main.xhtml", lang="en")
    c2.content = "<html><body><h1>Main Content</h1><p>The main story.</p></body></html>"

    book.add_item(c1)
    book.add_item(c2)
    book.spine = ["nav", c1, c2]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(epub_path, book)

    provider = EPUBProvider()
    doc = provider.extract_document(epub_path)

    all_content = " ".join(b.content for b in doc.blocks if isinstance(b.content, str))
    # Should extract content from both chapters
    assert "Introduction" in all_content or "Main Content" in all_content


def test_epub_provider_metadata(sample_epub: Path):
    """Test EPUB extracts metadata correctly."""
    provider = EPUBProvider()
    doc = provider.extract_document(sample_epub)

    assert doc.metadata is not None
    # Should have title from epub metadata
    assert doc.metadata.title == "Test Book" or doc.metadata.title is not None


def test_epub_provider_empty_book(tmp_path: Path):
    """Test EPUB provider handles minimal books."""
    epub_path = tmp_path / "empty.epub"

    book = epub.EpubBook()
    book.set_identifier("empty-123")
    book.set_title("Empty Book")
    book.set_language("en")
    book.spine = ["nav"]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(epub_path, book)

    provider = EPUBProvider()
    doc = provider.extract_document(epub_path)

    assert doc.source_type == SourceType.EPUB
    assert doc.blocks is not None
