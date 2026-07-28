"""Tests for JSONProvider."""

import json
from pathlib import Path

import pytest

from extractor.core.providers.json import JSONProvider
from extractor.core.schema.unified_document import SourceType


@pytest.fixture
def provider():
    """Return a JSONProvider instance for testing purposes."""
    return JSONProvider()


def test_json_basic_object(tmp_path: Path, provider):
    """Test extraction of a simple JSON object."""
    data = {"title": "Test Doc", "version": 2, "active": True}
    fp = tmp_path / "test.json"
    fp.write_text(json.dumps(data))

    doc = provider.extract_document(fp)

    assert doc.source_type == SourceType.JSON
    assert len(doc.blocks) >= 3
    all_text = " ".join(b.content for b in doc.blocks)
    assert "title" in all_text
    assert "Test Doc" in all_text


def test_json_nested_object(tmp_path: Path, provider):
    """Test extraction of nested JSON with depth."""
    data = {"outer": {"inner": {"deep": "value"}}}
    fp = tmp_path / "nested.json"
    fp.write_text(json.dumps(data))

    doc = provider.extract_document(fp)

    assert len(doc.blocks) >= 1
    all_text = " ".join(b.content for b in doc.blocks)
    assert "deep" in all_text
    assert "value" in all_text


def test_json_array(tmp_path: Path, provider):
    """Test extraction of a JSON array."""
    data = [{"name": "Alice"}, {"name": "Bob"}]
    fp = tmp_path / "array.json"
    fp.write_text(json.dumps(data))

    doc = provider.extract_document(fp)

    all_text = " ".join(b.content for b in doc.blocks)
    assert "Alice" in all_text
    assert "Bob" in all_text


def test_jsonl_extraction(tmp_path: Path, provider):
    """Test JSONL line-by-line parsing."""
    lines = [
        json.dumps({"id": 1, "text": "first"}),
        json.dumps({"id": 2, "text": "second"}),
        json.dumps({"id": 3, "text": "third"}),
    ]
    fp = tmp_path / "data.jsonl"
    fp.write_text("\n".join(lines))

    doc = provider.extract_document(fp)

    all_text = " ".join(b.content for b in doc.blocks)
    assert "first" in all_text
    assert "second" in all_text
    assert "third" in all_text
    # Should have Record headings
    assert "Record 1" in all_text


def test_jsonl_with_bad_lines(tmp_path: Path, provider):
    """Test JSONL gracefully handles malformed lines."""
    fp = tmp_path / "mixed.jsonl"
    fp.write_text('{"good": 1}\nnot json at all\n{"also_good": 2}\n')

    doc = provider.extract_document(fp)

    assert len(doc.blocks) >= 3  # 2 good records + headings + 1 bad line as text


def test_json_empty_file(tmp_path: Path, provider):
    """Test empty JSON file produces empty document."""
    fp = tmp_path / "empty.json"
    fp.write_text("")

    doc = provider.extract_document(fp)

    assert doc.source_type == SourceType.JSON
    assert len(doc.blocks) == 0


def test_json_malformed(tmp_path: Path, provider):
    """Test malformed JSON falls back to text block."""
    fp = tmp_path / "bad.json"
    fp.write_text("{not valid json content")

    doc = provider.extract_document(fp)

    assert len(doc.blocks) >= 1
    # Should have a block with parse_error attribute
    attrs = doc.blocks[0].metadata.attributes if doc.blocks[0].metadata else {}
    assert "parse_error" in attrs


def test_json_depth_limit(tmp_path: Path, provider):
    """Test recursion depth is limited."""
    # Build deeply nested structure
    data = "leaf"
    for i in range(15):
        data = {"level": data}
    fp = tmp_path / "deep.json"
    fp.write_text(json.dumps(data))

    doc = provider.extract_document(fp)

    # Should not crash, should produce blocks
    assert len(doc.blocks) >= 1


def test_json_null_values(tmp_path: Path, provider):
    """Test null values are handled."""
    fp = tmp_path / "nulls.json"
    fp.write_text(json.dumps({"key": None, "list": [None, 1, "text"]}))

    doc = provider.extract_document(fp)

    all_text = " ".join(b.content for b in doc.blocks)
    assert "null" in all_text


def test_json_unicode(tmp_path: Path, provider):
    """Test Unicode content is preserved."""
    fp = tmp_path / "unicode.json"
    fp.write_text(json.dumps({"text": "日本語テスト", "emoji": "🚀"}), encoding="utf-8")

    doc = provider.extract_document(fp)

    all_text = " ".join(b.content for b in doc.blocks)
    assert "日本語テスト" in all_text


def test_json_file_hash(tmp_path: Path, provider):
    """Test file hash is computed."""
    fp = tmp_path / "hash.json"
    fp.write_text('{"a": 1}')

    doc = provider.extract_document(fp)

    assert doc.metadata.file_hash
    assert len(doc.metadata.file_hash) == 32  # md5 hex
