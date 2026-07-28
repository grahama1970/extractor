#!/usr/bin/env python3
"""
Tests for the unified failure detection module.

Tests cover:
- Pattern detection for all file types
- Content quality issue detection
- Fix strategy registry
- PDF-specific pattern checks
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from extractor.failure_detector import (
    detect_failure_pattern,
    detect_content_issues,
    get_fix_strategies,
    FailurePattern,
    UNIVERSAL_PATTERNS,
    PDF_PATTERNS,
    OOXML_PATTERNS,
    HTML_PATTERNS,
    XML_PATTERNS,
    IMAGE_PATTERNS,
    PATTERNS_BY_TYPE,
)


class TestFailurePatternDataclass:
    """Tests for FailurePattern dataclass."""

    def test_create_failure_pattern(self):
        """Test creation and attribute assignment of a FailurePattern instance."""
        pattern = FailurePattern(
            name="test_pattern",
            description="Test description",
            file_type="pdf",
            severity="critical",
            fix_strategy="test_fix",
            details="Additional details",
        )

        assert pattern.name == "test_pattern"
        assert pattern.description == "Test description"
        assert pattern.file_type == "pdf"
        assert pattern.severity == "critical"
        assert pattern.fix_strategy == "test_fix"
        assert pattern.details == "Additional details"

    def test_failure_pattern_optional_details(self):
        """Verify FailurePattern details attribute is None when optional."""
        pattern = FailurePattern(
            name="test",
            description="desc",
            file_type="html",
            severity="warning",
            fix_strategy="fix",
        )

        assert pattern.details is None


class TestUniversalPatterns:
    """Tests for universal patterns that apply to all file types."""

    def test_file_not_found(self, tmp_path):
        """Detect failure pattern for a nonexistent PDF file."""
        nonexistent = tmp_path / "does_not_exist.pdf"
        pattern = detect_failure_pattern(nonexistent, "pdf")

        assert pattern is not None
        assert pattern.name == "file_not_found"
        assert pattern.severity == "critical"

    def test_empty_file(self, tmp_path):
        """Detect failure pattern from an empty PDF file."""
        empty_file = tmp_path / "empty.pdf"
        empty_file.touch()  # Create zero-byte file

        pattern = detect_failure_pattern(empty_file, "pdf")

        assert pattern is not None
        assert pattern.name == "empty_file"
        assert pattern.severity == "critical"

    def test_permission_denied(self, tmp_path):
        """Detect failure pattern from a given file and error type."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"PDF content")  # Non-empty file
        error = Exception("Permission denied: cannot read file")

        pattern = detect_failure_pattern(test_file, "pdf", error)

        assert pattern is not None
        assert pattern.name == "permission_denied"

    def test_timeout_error(self, tmp_path):
        """Detect failure pattern from a PDF file based on an error."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"PDF content")
        error = Exception("Operation timed out after 60 seconds")

        pattern = detect_failure_pattern(test_file, "pdf", error)

        assert pattern is not None
        assert pattern.name == "timeout"
        assert pattern.severity == "recoverable"

    def test_memory_error(self, tmp_path):
        """Test memory error pattern detection for PDF."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"PDF content")
        error = Exception("Out of memory allocating buffer")

        pattern = detect_failure_pattern(test_file, "pdf", error)

        assert pattern is not None
        assert pattern.name == "memory_error"

    def test_encoding_error(self, tmp_path):
        """Detect failure pattern for encoding errors in a text file."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"content")
        error = Exception("UnicodeDecodeError: codec can't decode byte")

        pattern = detect_failure_pattern(test_file, "txt", error)

        assert pattern is not None
        assert pattern.name == "encoding_error"


class TestPDFPatterns:
    """Tests for PDF-specific patterns."""

    def test_corrupted_pdf(self, tmp_path):
        """Test detection of corrupted PDF failure pattern."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"not a real pdf")
        error = Exception("FileDataError: cannot open document")

        pattern = detect_failure_pattern(test_file, "pdf", error)

        assert pattern is not None
        assert pattern.name == "corrupted_pdf"
        assert pattern.fix_strategy == "repair_pdf"

    def test_password_protected(self, tmp_path):
        """Detect failure pattern for a password-protected PDF document."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"encrypted pdf")
        error = Exception("Document is password protected")

        pattern = detect_failure_pattern(test_file, "pdf", error)

        assert pattern is not None
        assert pattern.name == "password_protected"
        assert pattern.fix_strategy == "request_password"


class TestOOXMLPatterns:
    """Tests for OOXML (DOCX/PPTX/XLSX) patterns."""

    def test_bad_zip_docx(self, tmp_path):
        """Detect failure pattern for invalid ZIP file in DOCX format."""
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"not a zip")
        error = Exception("BadZipFile: File is not a zip file")

        pattern = detect_failure_pattern(test_file, "docx", error)

        assert pattern is not None
        assert pattern.name == "bad_zip"
        assert pattern.fix_strategy == "repair_zip"

    def test_missing_content(self, tmp_path):
        """Test detection of missing content failure pattern."""
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"data")
        error = Exception("Missing document.xml in archive")

        pattern = detect_failure_pattern(test_file, "docx", error)

        assert pattern is not None
        assert pattern.name == "missing_content"


class TestHTMLPatterns:
    """Tests for HTML patterns."""

    def test_malformed_html(self, tmp_path):
        """Test malformed HTML pattern detection and strategy."""
        test_file = tmp_path / "test.html"
        test_file.write_text("<html><body>unclosed")
        error = Exception("HTML parser error: unexpected tag")

        pattern = detect_failure_pattern(test_file, "html", error)

        assert pattern is not None
        assert pattern.name == "malformed_html"
        assert pattern.fix_strategy == "sanitize_html"


class TestXMLPatterns:
    """Tests for XML patterns."""

    def test_xml_syntax_error(self, tmp_path):
        """Detect XML syntax errors and suggest repair strategies."""
        test_file = tmp_path / "test.xml"
        test_file.write_text("<root><unclosed>")
        error = Exception("XML syntax error at line 1")

        pattern = detect_failure_pattern(test_file, "xml", error)

        assert pattern is not None
        assert pattern.name == "xml_syntax_error"
        assert pattern.fix_strategy == "repair_xml"


class TestImagePatterns:
    """Tests for image patterns."""

    def test_corrupted_image(self, tmp_path):
        """Test detection of a corrupted image failure pattern."""
        test_file = tmp_path / "test.png"
        test_file.write_bytes(b"not an image")
        error = Exception("Image data is truncated or corrupt")

        pattern = detect_failure_pattern(test_file, "image", error)

        assert pattern is not None
        assert pattern.name == "corrupted_image"

    def test_unsupported_format(self, tmp_path):
        """Test unsupported format failure pattern detection."""
        test_file = tmp_path / "test.raw"
        test_file.write_bytes(b"raw data")
        # Use specific error that matches unsupported_format but not corrupted_image
        error = Exception("Unsupported format: RAW files not supported")

        pattern = detect_failure_pattern(test_file, "image", error)

        assert pattern is not None
        assert pattern.name == "unsupported_format"


class TestContentIssueDetection:
    """Tests for detect_content_issues function."""

    def test_empty_extraction(self):
        """Test detection of empty content extraction issue."""
        content = {"blocks": []}
        issues = detect_content_issues(content, "pdf")

        assert len(issues) >= 1
        issue_names = [i.name for i in issues]
        assert "empty_extraction" in issue_names

    def test_minimal_text(self):
        """Test detection of minimal text content issues."""
        content = {"blocks": [{"text": "Hi"}]}
        issues = detect_content_issues(content, "pdf")

        issue_names = [i.name for i in issues]
        assert "minimal_text" in issue_names

    def test_no_issues_for_good_content(self):
        """Check good content has no detected issues."""
        content = {
            "blocks": [
                {"text": "This is a substantial paragraph with plenty of text content that should pass the minimum threshold for extraction quality."},
                {"text": "Another paragraph with more content to ensure we have enough text."},
            ]
        }
        issues = detect_content_issues(content, "pdf")

        # Should not have empty_extraction or minimal_text
        issue_names = [i.name for i in issues]
        assert "empty_extraction" not in issue_names
        assert "minimal_text" not in issue_names

    def test_image_exempt_from_minimal_text(self):
        """Ensure images with alt text are exempt from minimal text warning."""
        content = {"blocks": [{"text": "Alt text"}]}
        issues = detect_content_issues(content, "image")

        # Images shouldn't trigger minimal_text warning
        issue_names = [i.name for i in issues]
        assert "minimal_text" not in issue_names


class TestFixStrategies:
    """Tests for get_fix_strategies function."""

    def test_returns_dict(self):
        """Confirm get_fix_strategies returns a dictionary."""
        strategies = get_fix_strategies()
        assert isinstance(strategies, dict)

    def test_all_strategies_have_descriptions(self):
        """Check all strategies have non-empty string descriptions."""
        strategies = get_fix_strategies()
        for name, description in strategies.items():
            assert isinstance(name, str)
            assert isinstance(description, str)
            assert len(description) > 0

    def test_known_strategies_exist(self):
        """Check if known strategies are present in the available strategies."""
        strategies = get_fix_strategies()
        expected = [
            "verify_path",
            "repair_pdf",
            "apply_ocr",
            "repair_zip",
            "sanitize_html",
            "normalize_text",
            "ask_human",
        ]
        for strategy in expected:
            assert strategy in strategies, f"Missing strategy: {strategy}"


class TestPatternsByType:
    """Tests for PATTERNS_BY_TYPE registry."""

    def test_all_file_types_covered(self):
        """Verify all expected file types are covered."""
        expected_types = [
            "pdf", "docx", "pptx", "spreadsheet",
            "html", "xml", "image", "markdown",
            "rst", "txt", "json", "epub",
        ]
        for file_type in expected_types:
            assert file_type in PATTERNS_BY_TYPE, f"Missing type: {file_type}"

    def test_all_types_include_universal_patterns(self):
        """Check if universal patterns are included in each file type."""
        for file_type, patterns in PATTERNS_BY_TYPE.items():
            # Universal patterns should be included
            universal_names = [p["name"] for p in UNIVERSAL_PATTERNS]
            type_names = [p["name"] for p in patterns]

            for universal_name in universal_names:
                assert universal_name in type_names, \
                    f"Type {file_type} missing universal pattern {universal_name}"

    def test_pattern_structure(self):
        """Validate pattern structures for required keys."""
        for file_type, patterns in PATTERNS_BY_TYPE.items():
            for pattern in patterns:
                assert "name" in pattern, f"Pattern missing name in {file_type}"
                assert "check" in pattern, f"Pattern missing check in {file_type}"
                assert "description" in pattern, f"Pattern missing description in {file_type}"
                assert "severity" in pattern, f"Pattern missing severity in {file_type}"
                assert "fix_strategy" in pattern, f"Pattern missing fix_strategy in {file_type}"


class TestUnknownErrors:
    """Tests for handling unknown errors."""

    def test_unknown_error_returns_pattern(self, tmp_path):
        """Verifies unknown error detection returns correct pattern."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"data")
        error = Exception("Completely unknown error type xyz123")

        pattern = detect_failure_pattern(test_file, "pdf", error)

        assert pattern is not None
        assert pattern.name == "unknown"
        assert pattern.fix_strategy == "ask_human"

    def test_no_error_no_pattern(self, tmp_path):
        """Detect failure pattern in a PDF file, returning None if absent."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"valid content here")

        pattern = detect_failure_pattern(test_file, "pdf", None)

        # No error means no pattern detected
        assert pattern is None
