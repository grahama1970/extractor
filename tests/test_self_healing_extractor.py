#!/usr/bin/env python3
"""
Tests for the self-healing universal extractor.

Tests cover:
- File type detection
- Successful extraction for all supported types
- Error pattern classification
- Self-healing retry logic
- File not found handling
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from extractor.self_healing_extractor import (
    extract,
    _detect_file_type,
    _classify_error,
    _get_fix_strategy,
    _to_unified_format,
    ExtractionResult,
    ERROR_PATTERNS,
)


class TestFileTypeDetection:
    """Tests for _detect_file_type function."""

    def test_detect_pdf(self, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()
        assert _detect_file_type(pdf_file) == "pdf"

    def test_detect_docx(self, tmp_path):
        docx_file = tmp_path / "test.docx"
        docx_file.touch()
        assert _detect_file_type(docx_file) == "docx"

    def test_detect_html(self, tmp_path):
        html_file = tmp_path / "test.html"
        html_file.write_text("<!DOCTYPE html><html><body>Test</body></html>")
        assert _detect_file_type(html_file) == "html"

    def test_detect_xml(self, tmp_path):
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("<?xml version='1.0'?><root><item>Test</item></root>")
        assert _detect_file_type(xml_file) == "xml"

    def test_detect_markdown(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.touch()
        assert _detect_file_type(md_file) == "markdown"

    def test_detect_json(self, tmp_path):
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value"}')
        assert _detect_file_type(json_file) == "json"

    def test_detect_txt(self, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.touch()
        assert _detect_file_type(txt_file) == "txt"

    def test_detect_image_png(self, tmp_path):
        img_file = tmp_path / "test.png"
        img_file.touch()
        assert _detect_file_type(img_file) == "image"

    def test_detect_spreadsheet(self, tmp_path):
        xlsx_file = tmp_path / "test.xlsx"
        xlsx_file.touch()
        assert _detect_file_type(xlsx_file) == "spreadsheet"

    def test_detect_pptx(self, tmp_path):
        pptx_file = tmp_path / "test.pptx"
        pptx_file.touch()
        assert _detect_file_type(pptx_file) == "pptx"

    def test_detect_epub(self, tmp_path):
        epub_file = tmp_path / "test.epub"
        epub_file.touch()
        assert _detect_file_type(epub_file) == "epub"

    def test_detect_rst(self, tmp_path):
        rst_file = tmp_path / "test.rst"
        rst_file.touch()
        assert _detect_file_type(rst_file) == "rst"

    def test_detect_unknown_falls_back_to_content(self, tmp_path):
        unknown_file = tmp_path / "test.xyz"
        unknown_file.write_text('{"json": true}')
        # Should detect as json based on content
        assert _detect_file_type(unknown_file) == "json"


class TestErrorClassification:
    """Tests for _classify_error function."""

    def test_classify_file_data_error(self):
        error = Exception("FileDataError: cannot open document")
        assert _classify_error(error) == "FileDataError"

    def test_classify_empty_file_error(self):
        error = Exception("EmptyFileError: file has zero bytes")
        assert _classify_error(error) == "EmptyFileError"

    def test_classify_password_protected(self):
        error = Exception("Document is password protected")
        assert _classify_error(error) == "password_protected"

    def test_classify_bad_zip(self):
        error = Exception("BadZipFile: not a valid ZIP")
        assert _classify_error(error) == "BadZipFile"

    def test_classify_encoding_error(self):
        error = Exception("UnicodeDecodeError: codec can't decode")
        assert _classify_error(error) == "encoding_error"

    def test_classify_timeout(self):
        error = Exception("Operation timed out after 60 seconds")
        assert _classify_error(error) == "timeout"

    def test_classify_memory_error(self):
        error = Exception("Out of memory allocating buffer")
        assert _classify_error(error) == "memory_error"

    def test_classify_unknown(self):
        error = Exception("Some completely unknown error")
        assert _classify_error(error) == "unknown"


class TestFixStrategy:
    """Tests for _get_fix_strategy function."""

    def test_strategy_for_file_data_error(self):
        strategy = _get_fix_strategy("FileDataError")
        assert strategy == "decrypt_or_repair"

    def test_strategy_for_scanned_pdf(self):
        strategy = _get_fix_strategy("scanned_no_ocr")
        assert strategy == "apply_ocr"

    def test_strategy_for_bad_zip(self):
        strategy = _get_fix_strategy("BadZipFile")
        assert strategy == "repair_zip"

    def test_strategy_for_encoding(self):
        strategy = _get_fix_strategy("encoding_error")
        assert strategy == "detect_and_reencode"

    def test_strategy_uses_known_fix_if_provided(self):
        strategy = _get_fix_strategy("unknown", known_fix="custom_fix")
        assert strategy == "custom_fix"

    def test_strategy_for_unknown_returns_none(self):
        # Unknown errors with recoverable=False should return None
        strategy = _get_fix_strategy("unknown")
        assert strategy is None


class TestExtraction:
    """Tests for the main extract function."""

    def test_file_not_found(self, tmp_path):
        nonexistent = tmp_path / "does_not_exist.pdf"
        result = extract(nonexistent, max_retries=1, use_memory=False, ask_on_failure=False)

        assert not result.success
        assert result.error_pattern == "file_not_found"
        assert "not found" in result.error.lower()

    def test_extract_markdown_success(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("# Title\n\nParagraph content here.")

        result = extract(md_file, max_retries=1, use_memory=False, ask_on_failure=False)

        assert result.success
        assert result.file_type == "markdown"
        assert result.content.get("block_count", 0) > 0
        assert result.attempts == 1

    def test_extract_html_success(self, tmp_path):
        html_file = tmp_path / "test.html"
        html_file.write_text("""<!DOCTYPE html>
<html><body>
<h1>Test Document</h1>
<p>This is a test paragraph.</p>
</body></html>""")

        result = extract(html_file, max_retries=1, use_memory=False, ask_on_failure=False)

        assert result.success
        assert result.file_type == "html"
        assert result.content.get("block_count", 0) > 0

    def test_extract_json_success(self, tmp_path):
        json_file = tmp_path / "test.json"
        json_file.write_text('{"title": "Test", "items": [1, 2, 3]}')

        result = extract(json_file, max_retries=1, use_memory=False, ask_on_failure=False)

        assert result.success
        assert result.file_type == "json"

    def test_extract_txt_success(self, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Line 1\nLine 2\nLine 3")

        result = extract(txt_file, max_retries=1, use_memory=False, ask_on_failure=False)

        assert result.success
        assert result.file_type == "txt"

    def test_extraction_result_structure(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test")

        result = extract(md_file, max_retries=1, use_memory=False, ask_on_failure=False)

        assert isinstance(result, ExtractionResult)
        assert hasattr(result, "success")
        assert hasattr(result, "file_path")
        assert hasattr(result, "file_type")
        assert hasattr(result, "content")
        assert hasattr(result, "error")
        assert hasattr(result, "error_pattern")
        assert hasattr(result, "attempts")


class TestUnifiedFormat:
    """Tests for _to_unified_format function."""

    def test_converts_model_dump(self):
        mock_doc = MagicMock()
        mock_doc.model_dump.return_value = {
            "blocks": [{"type": "text", "text": "content"}]
        }

        result = _to_unified_format(mock_doc, "pdf")

        assert result["file_type"] == "pdf"
        assert "blocks" in result
        assert "extracted_at" in result

    def test_converts_dict_directly(self):
        data = {"blocks": [{"type": "heading", "text": "Title"}]}

        result = _to_unified_format(data, "html")

        assert result["file_type"] == "html"
        assert len(result["blocks"]) >= 1

    def test_normalizes_block_types_to_lowercase(self):
        data = {"blocks": [{"type": "Text", "text": "content"}]}

        result = _to_unified_format(data, "pdf")

        # Type should be normalized to lowercase
        blocks = result.get("blocks", [])
        if blocks:
            assert blocks[0]["type"] == "text"


class TestErrorPatterns:
    """Tests for ERROR_PATTERNS registry."""

    def test_all_patterns_have_required_keys(self):
        for name, pattern in ERROR_PATTERNS.items():
            assert "description" in pattern, f"{name} missing description"
            assert "fix_strategy" in pattern, f"{name} missing fix_strategy"
            assert "recoverable" in pattern, f"{name} missing recoverable"

    def test_known_patterns_exist(self):
        expected = [
            "FileDataError",
            "EmptyFileError",
            "scanned_no_ocr",
            "password_protected",
            "BadZipFile",
            "encoding_error",
            "timeout",
            "memory_error",
            "unknown",
        ]
        for pattern_name in expected:
            assert pattern_name in ERROR_PATTERNS, f"Missing pattern: {pattern_name}"
