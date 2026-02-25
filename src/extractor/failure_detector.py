#!/usr/bin/env python3
"""
Unified Failure Detection - Detects extraction failure patterns across ALL file types.

This module provides pattern detection that works identically for:
PDF, DOCX, PPTX, XLSX, HTML, XML, Markdown, RST, EPUB, TXT, JSON, Images

The self_healing_extractor uses this to classify errors and select fix strategies.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class FailurePattern:
    """A detected failure pattern."""

    name: str
    description: str
    file_type: str
    severity: str  # "critical", "recoverable", "warning"
    fix_strategy: str
    details: Optional[str] = None


# Universal patterns that apply to ALL file types
UNIVERSAL_PATTERNS = [
    {
        "name": "file_not_found",
        "check": lambda p, e: not Path(p).exists(),
        "description": "File does not exist",
        "severity": "critical",
        "fix_strategy": "verify_path",
    },
    {
        "name": "empty_file",
        "check": lambda p, e: Path(p).exists() and Path(p).stat().st_size == 0,
        "description": "File is empty (zero bytes)",
        "severity": "critical",
        "fix_strategy": "check_source",
    },
    {
        "name": "permission_denied",
        "check": lambda p, e: "permission" in str(e).lower(),
        "description": "Cannot read file - permission denied",
        "severity": "critical",
        "fix_strategy": "fix_permissions",
    },
    {
        "name": "timeout",
        "check": lambda p, e: "timeout" in str(e).lower() or "timed out" in str(e).lower(),
        "description": "Operation timed out",
        "severity": "recoverable",
        "fix_strategy": "chunk_and_retry",
    },
    {
        "name": "memory_error",
        "check": lambda p, e: "memory" in str(e).lower() or "oom" in str(e).lower(),
        "description": "Out of memory",
        "severity": "recoverable",
        "fix_strategy": "stream_process",
    },
    {
        "name": "encoding_error",
        "check": lambda p, e: any(
            x in str(e).lower() for x in ["encode", "decode", "codec", "utf"]
        ),
        "description": "Character encoding issue",
        "severity": "recoverable",
        "fix_strategy": "detect_and_reencode",
    },
]

# PDF-specific patterns
PDF_PATTERNS = [
    {
        "name": "corrupted_pdf",
        "check": lambda p, e: any(
            x in str(e).lower()
            for x in ["filedataerror", "cannot open", "not a pdf", "pdf structure"]
        ),
        "description": "Corrupted or invalid PDF",
        "severity": "recoverable",
        "fix_strategy": "repair_pdf",
    },
    {
        "name": "password_protected",
        "check": lambda p, e: any(
            x in str(e).lower() for x in ["password", "encrypted", "protected"]
        ),
        "description": "Password-protected PDF",
        "severity": "recoverable",
        "fix_strategy": "request_password",
    },
    {
        "name": "scanned_no_ocr",
        "check": lambda p, e: _check_scanned_pdf(p),
        "description": "Scanned PDF without text layer",
        "severity": "recoverable",
        "fix_strategy": "apply_ocr",
    },
    {
        "name": "header_footer_bleed",
        "check": lambda p, e: False,  # Detected during extraction, not error
        "description": "Header/footer content bleeding into body",
        "severity": "warning",
        "fix_strategy": "filter_margins",
    },
    {
        "name": "multi_column_layout",
        "check": lambda p, e: False,  # Detected during extraction
        "description": "Multi-column layout may affect reading order",
        "severity": "warning",
        "fix_strategy": "column_detection",
    },
]

# DOCX/PPTX/XLSX (OOXML) patterns
OOXML_PATTERNS = [
    {
        "name": "bad_zip",
        "check": lambda p, e: any(
            x in str(e).lower() for x in ["bad zip", "not a zip", "zipfile"]
        ),
        "description": "Corrupted ZIP structure (Office file is a ZIP)",
        "severity": "recoverable",
        "fix_strategy": "repair_zip",
    },
    {
        "name": "missing_content",
        "check": lambda p, e: "content.xml" in str(e).lower() or "document.xml" in str(e).lower(),
        "description": "Missing core content file",
        "severity": "critical",
        "fix_strategy": "extract_partial",
    },
    {
        "name": "ole_format",
        "check": lambda p, e: "ole" in str(e).lower() or ".doc" in str(p).lower(),
        "description": "Legacy OLE format (pre-2007)",
        "severity": "recoverable",
        "fix_strategy": "use_legacy_parser",
    },
]

# HTML patterns
HTML_PATTERNS = [
    {
        "name": "malformed_html",
        "check": lambda p, e: any(
            x in str(e).lower() for x in ["html", "parser error", "tag"]
        ),
        "description": "Malformed HTML structure",
        "severity": "recoverable",
        "fix_strategy": "sanitize_html",
    },
    {
        "name": "script_heavy",
        "check": lambda p, e: _check_script_heavy_html(p),
        "description": "JavaScript-heavy page (content may be dynamic)",
        "severity": "warning",
        "fix_strategy": "browser_render",
    },
]

# XML patterns
XML_PATTERNS = [
    {
        "name": "xml_syntax_error",
        "check": lambda p, e: any(
            x in str(e).lower() for x in ["xml", "syntax", "parsing", "element"]
        ),
        "description": "XML syntax error",
        "severity": "recoverable",
        "fix_strategy": "repair_xml",
    },
    {
        "name": "invalid_dtd",
        "check": lambda p, e: "dtd" in str(e).lower() or "doctype" in str(e).lower(),
        "description": "Invalid or missing DTD/schema",
        "severity": "warning",
        "fix_strategy": "ignore_schema",
    },
]

# Image patterns
IMAGE_PATTERNS = [
    {
        "name": "corrupted_image",
        "check": lambda p, e: any(
            x in str(e).lower() for x in ["image", "truncated", "corrupt"]
        ),
        "description": "Corrupted or truncated image",
        "severity": "recoverable",
        "fix_strategy": "repair_image",
    },
    {
        "name": "unsupported_format",
        "check": lambda p, e: "unsupported" in str(e).lower() or "format" in str(e).lower(),
        "description": "Unsupported image format",
        "severity": "recoverable",
        "fix_strategy": "convert_format",
    },
]

# All patterns by file type
PATTERNS_BY_TYPE = {
    "pdf": UNIVERSAL_PATTERNS + PDF_PATTERNS,
    "docx": UNIVERSAL_PATTERNS + OOXML_PATTERNS,
    "pptx": UNIVERSAL_PATTERNS + OOXML_PATTERNS,
    "spreadsheet": UNIVERSAL_PATTERNS + OOXML_PATTERNS,
    "html": UNIVERSAL_PATTERNS + HTML_PATTERNS,
    "xml": UNIVERSAL_PATTERNS + XML_PATTERNS,
    "image": UNIVERSAL_PATTERNS + IMAGE_PATTERNS,
    "markdown": UNIVERSAL_PATTERNS,
    "rst": UNIVERSAL_PATTERNS,
    "txt": UNIVERSAL_PATTERNS,
    "json": UNIVERSAL_PATTERNS,
    "epub": UNIVERSAL_PATTERNS + OOXML_PATTERNS,  # EPUB is also ZIP-based
}


def detect_failure_pattern(
    file_path: str | Path,
    file_type: str,
    error: Optional[Exception] = None,
) -> Optional[FailurePattern]:
    """
    Detect the failure pattern for a failed extraction.

    Args:
        file_path: Path to the file
        file_type: Detected file type
        error: The exception that was raised (if any)

    Returns:
        FailurePattern if detected, None otherwise
    """
    path = Path(file_path)
    error_str = str(error) if error else ""

    # Get patterns for this file type
    patterns = PATTERNS_BY_TYPE.get(file_type, UNIVERSAL_PATTERNS)

    for pattern in patterns:
        try:
            if pattern["check"](str(path), error_str):
                return FailurePattern(
                    name=pattern["name"],
                    description=pattern["description"],
                    file_type=file_type,
                    severity=pattern["severity"],
                    fix_strategy=pattern["fix_strategy"],
                    details=error_str[:200] if error_str else None,
                )
        except Exception:
            continue

    # Unknown pattern
    if error:
        return FailurePattern(
            name="unknown",
            description="Unknown error",
            file_type=file_type,
            severity="critical",
            fix_strategy="ask_human",
            details=error_str[:200],
        )

    return None


def detect_content_issues(content: dict, file_type: str) -> list[FailurePattern]:
    """
    Detect quality issues in extracted content (not errors, but warnings).

    Args:
        content: Extracted content dictionary
        file_type: File type

    Returns:
        List of warning patterns
    """
    issues = []

    blocks = content.get("blocks", [])

    # Check for empty extraction
    if not blocks:
        issues.append(
            FailurePattern(
                name="empty_extraction",
                description="No content blocks extracted",
                file_type=file_type,
                severity="warning",
                fix_strategy="try_alternate_parser",
            )
        )

    # Check for very little text
    total_text = sum(len(b.get("text", "")) for b in blocks)
    if total_text < 100 and file_type not in ("image",):
        issues.append(
            FailurePattern(
                name="minimal_text",
                description=f"Very little text extracted ({total_text} chars)",
                file_type=file_type,
                severity="warning",
                fix_strategy="check_encoding_or_ocr",
            )
        )

    # PDF-specific content checks
    if file_type == "pdf":
        issues.extend(_check_pdf_content_issues(blocks))

    return issues


def _check_pdf_content_issues(blocks: list) -> list[FailurePattern]:
    """Check PDF-specific content quality issues."""
    issues = []

    # Check for header/footer patterns
    header_patterns = [
        r"^\s*page\s+\d+\s*$",
        r"^\s*\d+\s*$",
        r"confidential|proprietary|draft",
        r"copyright\s*©?\s*\d{4}",
    ]

    header_footer_count = 0
    for block in blocks:
        text = block.get("text", "").strip().lower()
        for pattern in header_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                header_footer_count += 1
                break

    if header_footer_count > len(blocks) * 0.1:  # >10% are headers/footers
        issues.append(
            FailurePattern(
                name="excessive_headers_footers",
                description=f"Many header/footer blocks detected ({header_footer_count})",
                file_type="pdf",
                severity="warning",
                fix_strategy="filter_margins",
            )
        )

    # Check for encoding issues (curly quotes, etc.)
    encoding_chars = 0
    for block in blocks:
        text = block.get("text", "")
        if re.search(r"[\u2018\u2019\u201c\u201d\u2014\u2013\u2026]", text):
            encoding_chars += 1

    if encoding_chars > 0:
        issues.append(
            FailurePattern(
                name="special_encoding",
                description=f"Special characters detected ({encoding_chars} blocks)",
                file_type="pdf",
                severity="warning",
                fix_strategy="normalize_text",
            )
        )

    return issues


def _check_scanned_pdf(path: str) -> bool:
    """Check if PDF is scanned (images without text)."""
    try:
        import fitz

        doc = fitz.open(path)
        text_pages = 0
        image_pages = 0

        for page in doc:
            text = page.get_text().strip()
            images = page.get_images()

            if len(text) > 50:
                text_pages += 1
            if images and len(text) < 50:
                image_pages += 1

        doc.close()

        return image_pages > text_pages and image_pages > len(doc) * 0.5
    except Exception:
        return False


def _check_script_heavy_html(path: str) -> bool:
    """Check if HTML is JavaScript-heavy."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        script_count = content.lower().count("<script")
        content_length = len(content)

        # Heuristic: >10 scripts or scripts are >20% of content
        return script_count > 10 or (script_count > 0 and script_count * 1000 > content_length * 0.2)
    except Exception:
        return False


def get_fix_strategies() -> dict[str, str]:
    """Get all available fix strategies and their descriptions."""
    return {
        "verify_path": "Verify the file path is correct",
        "check_source": "Check the source of the file",
        "fix_permissions": "Fix file permissions",
        "chunk_and_retry": "Process in smaller chunks",
        "stream_process": "Use streaming to reduce memory",
        "detect_and_reencode": "Detect encoding and convert to UTF-8",
        "repair_pdf": "Attempt to repair PDF structure",
        "request_password": "Ask user for document password",
        "apply_ocr": "Apply OCR to extract text from images",
        "filter_margins": "Filter header/footer content",
        "column_detection": "Detect and handle multi-column layout",
        "repair_zip": "Repair corrupted ZIP structure",
        "extract_partial": "Extract whatever content is accessible",
        "use_legacy_parser": "Use legacy format parser",
        "sanitize_html": "Clean up malformed HTML",
        "browser_render": "Render in browser to get dynamic content",
        "repair_xml": "Repair XML syntax errors",
        "ignore_schema": "Ignore DTD/schema validation",
        "repair_image": "Attempt to repair image data",
        "convert_format": "Convert to supported format",
        "try_alternate_parser": "Try a different extraction library",
        "check_encoding_or_ocr": "Check encoding or apply OCR",
        "normalize_text": "Normalize special characters",
        "ask_human": "Ask user for guidance via /interview",
    }
