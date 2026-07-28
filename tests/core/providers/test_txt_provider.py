"""Tests for TXTProvider."""

from pathlib import Path

import pytest

from extractor.core.providers.txt import TXTProvider
from extractor.core.schema.unified_document import SourceType


@pytest.fixture
def provider():
    """Return an instance of the TXTProvider class."""
    return TXTProvider()


def test_txt_basic_extraction(tmp_path: Path, provider):
    """Test basic text extraction returns content."""
    fp = tmp_path / "test.txt"
    fp.write_text("Hello world.\nThis is a test document.\n")

    doc = provider.extract_document(fp)

    assert doc.source_type == SourceType.TXT
    assert len(doc.blocks) >= 1
    all_text = " ".join(b.content for b in doc.blocks)
    assert "Hello world" in all_text


def test_txt_chapter_detection(tmp_path: Path, provider):
    """Test chapter-based structure detection."""
    content = """Chapter 1: Introduction

This is the introduction to the document.
It has multiple paragraphs of content.

Chapter 2: Methods

This chapter describes the methodology.
Several approaches were considered.

Chapter 3: Conclusion

Final thoughts and summary.
"""
    fp = tmp_path / "chapters.txt"
    fp.write_text(content)

    doc = provider.extract_document(fp)

    assert len(doc.blocks) >= 3
    all_text = " ".join(b.content for b in doc.blocks)
    assert "Introduction" in all_text
    assert "Methods" in all_text
    assert "Conclusion" in all_text


def test_txt_empty_file(tmp_path: Path, provider):
    """Test empty file produces document with minimal blocks."""
    fp = tmp_path / "empty.txt"
    fp.write_text("")

    doc = provider.extract_document(fp)

    assert doc.source_type == SourceType.TXT
    assert doc.blocks is not None


def test_txt_unicode(tmp_path: Path, provider):
    """Test UTF-8 content is handled."""
    fp = tmp_path / "unicode.txt"
    fp.write_text("Ñoño café résumé 日本語\n", encoding="utf-8")

    doc = provider.extract_document(fp)

    all_text = " ".join(b.content for b in doc.blocks)
    assert "café" in all_text


def test_txt_latin1_fallback(tmp_path: Path, provider):
    """Test latin-1 fallback for non-UTF8 files."""
    fp = tmp_path / "latin.txt"
    fp.write_bytes(b"caf\xe9 r\xe9sum\xe9\n")  # latin-1 encoded

    doc = provider.extract_document(fp)

    assert len(doc.blocks) >= 1
    all_text = " ".join(b.content for b in doc.blocks)
    assert "café" in all_text


def test_txt_large_single_section(tmp_path: Path, provider):
    """Test a large text with no chapter markers is treated as single section."""
    content = "This is line {}.\n" * 100
    fp = tmp_path / "long.txt"
    fp.write_text(content.format(*range(100)))

    doc = provider.extract_document(fp)

    assert len(doc.blocks) >= 1


def test_txt_log_extension(tmp_path: Path, provider):
    """Test .log files are handled like .txt."""
    fp = tmp_path / "app.log"
    fp.write_text("2026-01-01 INFO Starting application\n2026-01-01 ERROR Something failed\n")

    doc = provider.extract_document(fp)

    all_text = " ".join(b.content for b in doc.blocks)
    assert "Starting application" in all_text
