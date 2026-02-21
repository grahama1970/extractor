"""Section, formula, and requirement detection for Stage-00 profile detection.

Provides regex-based and font-based section counting, formula detection,
section style detection, and requirement pattern matching.

Inputs: Raw text or pre-collected font data from PDF pages
Outputs: Section counts, style info, boolean flags
Failure: Returns zero-count dicts or False on any exception
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from typing import Any, Dict, Optional

from loguru import logger

try:
    import fitz
    _HAVE_FITZ = True
except ImportError:
    _HAVE_FITZ = False

# Formula/equation detection patterns
FORMULA_PATTERNS = [
    r"\$\$.+?\$\$",
    r"\$[^$]+\$",
    r"\\begin\{equation\}",
    r"\\frac\{",
    r"\\sum|\\int|\\prod",
    r"\\alpha|\\beta|\\gamma|\\theta|\\pi",
    r"[∑∫∂√∞±×÷≤≥≠≈]",
]

# Section style patterns
SECTION_PATTERNS = {
    "decimal": r"^\d+\.\d+",
    "roman": r"^[IVXLCDM]+\.",
    "chapter": r"^Chapter\s+\d+",
    "markdown": r"^#{1,6}\s+",
}

# Comprehensive section counting patterns
SECTION_COUNT_PATTERNS = [
    r"^\s*\d+(?:\.\d+)*(?:\.[a-z])?[.:)\-–—\s]",
    r"^\s*(?:Appendix|Annex|Section|Chapter|Part)\s+[A-Za-z0-9IVXLCDM.]+",
    r"^\s*[IVXLCDM]+\.\s+[A-Z]",
    r"^\s*[A-Z]\.\s+[A-Z]",
]

# Common header titles
COMMON_HEADERS = {
    "abstract", "introduction", "conclusion", "summary", "overview",
    "background", "methods", "results", "discussion", "references",
    "appendix", "glossary", "acronyms", "definitions", "requirements",
    "scope", "purpose", "architecture", "design", "implementation",
}

# Requirement patterns
REQUIREMENT_PATTERNS = [
    r"REQ-\d+",
    r"\bSHALL\b",
    r"\bMUST\b",
    r"\bSHOULD\b",
]


def detect_formulas(text: str) -> bool:
    """Check for LaTeX or math formulas in text."""
    for pat in FORMULA_PATTERNS:
        if re.search(pat, text, re.MULTILINE | re.DOTALL):
            return True
    return False


def detect_section_style(text: str) -> Optional[str]:
    """Detect section numbering style."""
    for style, pat in SECTION_PATTERNS.items():
        if re.search(pat, text, re.MULTILINE | re.IGNORECASE):
            return style
    return None


def detect_requirements(text: str) -> bool:
    """Check for requirement patterns."""
    for pat in REQUIREMENT_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def estimate_section_count(text: str) -> Dict[str, Any]:
    """Estimate number of sections using regex patterns.

    Returns dict with:
        - estimated_count: Total unique section matches
        - by_pattern: Breakdown by pattern type
        - common_headers: Count of common header titles found
    """
    lines = text.split("\n")

    counts = {"decimal": 0, "labeled": 0, "roman": 0, "alpha": 0}
    seen_numbers: set[str] = set()

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped or len(line_stripped) < 3:
            continue

        for i, pat in enumerate(SECTION_COUNT_PATTERNS):
            match = re.match(pat, line_stripped, re.IGNORECASE)
            if match:
                matched_text = match.group(0).strip()[:20]
                if matched_text not in seen_numbers:
                    seen_numbers.add(matched_text)
                    pattern_names = ["decimal", "labeled", "roman", "alpha"]
                    counts[pattern_names[i]] += 1
                break

    header_count = 0
    text_lower = text.lower()
    for header in COMMON_HEADERS:
        if re.search(rf"(?:^|\d\.?\s+){header}\b", text_lower, re.MULTILINE):
            header_count += 1

    total = sum(counts.values())

    return {
        "estimated_count": total,
        "by_pattern": counts,
        "common_headers_found": header_count,
        "primary_style": max(counts, key=counts.get) if total > 0 else None,
    }


def estimate_section_count_by_font(
    pdf_path: "Path",
    sample_pages: int = 20,
) -> Dict[str, Any]:
    """Estimate section count using font-size metadata from PyMuPDF.

    Opens the PDF with fitz, samples pages spread across the document, and
    uses font size + bold flags to identify heading lines.  This is far more
    accurate than regex on markdown text because pymupdf4llm strips font
    metadata.

    Sampling strategy: spreads pages evenly across the document to avoid
    front-matter bias (first pages are often title/TOC with few headings).
    """
    from pathlib import Path as _Path

    if not _HAVE_FITZ:
        return {"estimated_count": 0, "sampled_count": 0, "pages_sampled": 0,
                "body_font_size": 0, "error": "fitz not available"}

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        logger.warning(f"Font estimation failed to open PDF: {e}")
        return {"estimated_count": 0, "sampled_count": 0, "pages_sampled": 0,
                "body_font_size": 0, "error": str(e)}

    total_pages = len(doc)
    pages_to_sample = min(sample_pages, total_pages)

    if pages_to_sample >= total_pages:
        sample_indices = list(range(total_pages))
    else:
        step = total_pages / pages_to_sample
        sample_indices = [int(i * step) for i in range(pages_to_sample)]

    caption_re = re.compile(
        r"^\s*(?:Table|Figure|Fig\.?|Listing|Algorithm|Exhibit)\s+\d",
        re.IGNORECASE,
    )
    section_number_re = re.compile(
        r"^\s*(?:"
        r"\d{1,2}(?:\.\d{1,3}){0,3}"
        r"|[A-Z](?:\.\d{1,3}){0,2}"
        r"|[IVXLC]{1,5}"
        r")\s+[A-Z]",
    )

    all_sizes: list[float] = []
    page_lines: list[list[dict]] = []

    for page_idx in sample_indices:
        page = doc[page_idx]
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

        lines_on_page: list[dict] = []
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                for span in spans:
                    size = span.get("size", 0)
                    text = span.get("text", "").strip()
                    if size > 0 and len(text) > 0:
                        all_sizes.append(size)

                first_span = spans[0]
                line_text = "".join(s.get("text", "") for s in spans).strip()
                lines_on_page.append({
                    "text": line_text,
                    "size": first_span.get("size", 0),
                    "flags": first_span.get("flags", 0),
                    "font": first_span.get("font", ""),
                })

        page_lines.append(lines_on_page)

    doc.close()

    return estimate_sections_from_font_data(
        all_sizes, page_lines, pages_to_sample, total_pages,
        caption_re, section_number_re,
    )


def estimate_sections_from_font_data(
    all_sizes: list,
    page_lines: list,
    pages_sampled: int,
    total_pages: int,
    caption_re: "re.Pattern | None" = None,
    section_number_re: "re.Pattern | None" = None,
) -> Dict[str, Any]:
    """Estimate section count from pre-collected font data (no PDF re-open).

    Logic ported from estimate_section_count_by_font() but operates on
    data already collected during the single-pass page loop.
    """
    if not all_sizes:
        return {"estimated_count": 0, "sampled_count": 0,
                "pages_sampled": pages_sampled, "body_font_size": 0}

    if caption_re is None:
        caption_re = re.compile(
            r"^\s*(?:Table|Figure|Fig\.?|Listing|Algorithm|Exhibit)\s+\d",
            re.IGNORECASE,
        )
    if section_number_re is None:
        section_number_re = re.compile(
            r"^\s*(?:"
            r"\d{1,2}(?:\.\d{1,3}){0,3}"
            r"|[A-Z](?:\.\d{1,3}){0,2}"
            r"|[IVXLC]{1,5}"
            r")\s+[A-Z]",
        )

    rounded = [round(s, 1) for s in all_sizes]
    paragraph_sizes = [s for s in rounded if s >= 8.0]
    if paragraph_sizes:
        body_size = Counter(paragraph_sizes).most_common(1)[0][0]
    else:
        body_size = statistics.median(all_sizes)

    heading_threshold = max(body_size * 1.18, 9.5)
    heading_count = 0
    seen_texts: set[str] = set()

    for lines in page_lines:
        page_headings = 0
        for line_info in lines:
            text = line_info["text"]
            size = line_info["size"]
            flags = line_info.get("flags", 0)
            is_bold = bool(flags & 16)

            if len(text) < 2 or len(text) > 120:
                continue
            if caption_re.match(text):
                continue
            if text.isdigit():
                continue

            is_heading = False
            if size >= heading_threshold:
                is_heading = True
            elif is_bold and size > body_size * 1.10 and size >= 9.0:
                is_heading = True
            elif is_bold and abs(size - body_size) < 1.0 and len(text) < 80:
                if section_number_re.match(text):
                    is_heading = True
                elif len(text) < 50 and text[0].isupper() and not text[0].isdigit():
                    if len(text.split()) <= 6:
                        is_heading = True

            if is_heading:
                normalized = text.strip().lower()[:60]
                if normalized not in seen_texts:
                    seen_texts.add(normalized)
                    heading_count += 1
                    page_headings += 1
                if page_headings >= 8:
                    break

    if pages_sampled < total_pages and pages_sampled > 0:
        extrapolated = int((heading_count / pages_sampled) * total_pages)
    else:
        extrapolated = heading_count

    return {
        "estimated_count": extrapolated,
        "sampled_count": heading_count,
        "pages_sampled": pages_sampled,
        "body_font_size": round(body_size, 1),
    }
