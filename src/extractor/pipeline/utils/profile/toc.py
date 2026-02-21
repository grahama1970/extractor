"""Table of Contents extraction for Stage-00 profile detection.

Strategies (in priority order):
1. PyMuPDF embedded bookmarks (doc.get_toc) — authoritative when present
2. Text-based TOC scan — regex patterns on first 10 pages
3. HURIDOCS vision-based extraction — Docker service fallback

Inputs: PDF path or open fitz.Document
Outputs: Dict with has_toc, source, entries, entry_count, max_depth, page_coverage
Failure: Returns empty TOC dict with error key on any exception
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List

from loguru import logger

try:
    import fitz
    _HAVE_FITZ = True
except ImportError:
    _HAVE_FITZ = False

# TOC entry pattern for parsing structured entries
TOC_ENTRY_PATTERN = re.compile(
    r'^(?P<num>[\d.]+|[IVXLCDM]+\.?|[A-Z]\.?)?\s*(?P<title>.+?)\s*[.\-·…_]{0,}?\s*(?P<page>\d+)?\s*$'
)

# HURIDOCS Docker service configuration
_HURIDOCS_TOC_URL = os.environ.get("HURIDOCS_TOC_URL", "")
_HURIDOCS_TOC_TIMEOUT = int(os.environ.get("HURIDOCS_TOC_TIMEOUT", "120"))
_HURIDOCS_TOC_FAST = os.environ.get("HURIDOCS_TOC_FAST", "true").lower() == "true"


def _empty_toc(**extra: Any) -> Dict[str, Any]:
    """Return an empty TOC result dict."""
    result = {
        "has_toc": False, "source": None, "entries": [],
        "entry_count": 0, "max_depth": 0, "page_coverage": [],
    }
    result.update(extra)
    return result


def extract_toc(pdf_path: Path) -> Dict[str, Any]:
    """Extract Table of Contents from PDF.

    Strategy:
    1. Try PyMuPDF's get_toc() for embedded bookmarks (authoritative if present)
    2. If no embedded TOC, scan first pages for text-based TOC patterns
    3. Try HURIDOCS vision-based extraction as final fallback

    Returns:
        {
            "has_toc": bool,
            "source": "embedded" | "text_detected" | "huridocs_vision" | None,
            "entries": [{"level": int, "title": str, "page": int}, ...],
            "entry_count": int,
            "max_depth": int,
            "page_coverage": list[int],
        }
    """
    if not _HAVE_FITZ:
        return _empty_toc(error="fitz not available")

    try:
        doc = fitz.open(pdf_path)
        result = extract_toc_from_doc(doc)
        doc.close()

        # If nothing found from embedded/text, try HURIDOCS
        if not result.get("has_toc"):
            huridocs_entries = _extract_toc_via_huridocs(pdf_path)
            if huridocs_entries:
                pages_covered = {e["page"] for e in huridocs_entries if e.get("page", 0) > 0}
                max_depth = max((e.get("level", 1) for e in huridocs_entries), default=1)
                logger.info(f"HURIDOCS vision TOC: {len(huridocs_entries)} entries")
                return {
                    "has_toc": True, "source": "huridocs_vision",
                    "entries": huridocs_entries,
                    "entry_count": len(huridocs_entries),
                    "max_depth": max_depth,
                    "page_coverage": sorted(pages_covered),
                }

        return result

    except Exception as e:
        logger.warning(f"TOC extraction failed: {e}")
        return _empty_toc(error=str(e))


def extract_toc_from_doc(doc: Any) -> Dict[str, Any]:
    """Extract TOC from an already-open fitz.Document (no re-open).

    Combines embedded bookmarks (doc.get_toc) with text-based TOC scan.
    """
    try:
        toc = doc.get_toc()
        if toc:
            entries = []
            pages_covered: set[int] = set()
            max_depth = 0
            for item in toc:
                level = item[0] if len(item) > 0 else 1
                title = " ".join((item[1] if len(item) > 1 else "").split())
                page = item[2] if len(item) > 2 else 0
                if not title.strip():
                    continue
                entries.append({"level": level, "title": title, "page": page})
                if page > 0:
                    pages_covered.add(page)
                max_depth = max(max_depth, level)

            logger.info(f"Extracted embedded TOC: {len(entries)} entries, depth={max_depth}")
            return {
                "has_toc": True, "source": "embedded", "entries": entries,
                "entry_count": len(entries), "max_depth": max_depth,
                "page_coverage": sorted(pages_covered),
            }

        # Text-based TOC scan
        entries = _detect_text_based_toc(doc)
        if entries:
            pages_covered = {e["page"] for e in entries if e.get("page", 0) > 0}
            max_depth = max((e.get("level", 1) for e in entries), default=1)
            logger.info(f"Detected text-based TOC: {len(entries)} entries")
            return {
                "has_toc": True, "source": "text_detected", "entries": entries,
                "entry_count": len(entries), "max_depth": max_depth,
                "page_coverage": sorted(pages_covered),
            }

        return _empty_toc()

    except Exception as e:
        logger.warning(f"TOC extraction failed: {e}")
        return _empty_toc(error=str(e))


def _detect_text_based_toc(doc: Any) -> List[Dict[str, Any]]:
    """Detect TOC entries from page text when no embedded TOC exists.

    Uses proven patterns from text_toolz for robust detection.
    Scans first 10 pages looking for:
    1. A "Table of Contents" or "Contents" heading
    2. Followed by numbered entries with page numbers
    """
    entries: List[Dict[str, Any]] = []

    toc_header_patterns = [
        r"^\s*table\s+of\s+contents\s*$",
        r"^\s*contents\s*$",
        r"^\s*toc\s*$",
    ]

    space_pattern = r"[ \t\u202c\u202d]"
    toc_entry_pattern = re.compile(
        rf"""
        ^{space_pattern}*           # Start with optional whitespace
        (?P<num>\d+(?:\.\d+)*)      # Section number: 3, 3.1, 3.1.1
        \s+                          # Space after number
        (?P<title>[^\d\n].{{2,60}})  # Title text (non-digit start, 2-60 chars)
        [\.\s]+                      # Dots or spaces (TOC leader)
        (?P<page>\d{{1,4}})          # Page number
        {space_pattern}*$            # End with optional whitespace
        """,
        re.VERBOSE | re.MULTILINE,
    )

    roman_pattern = re.compile(
        rf"""
        ^{space_pattern}*
        (?P<num>[IVXLCDM]+\.?)       # Roman numeral
        \s+
        (?P<title>[A-Z][^\d\n]{{2,50}})
        [\.\s]+
        (?P<page>\d{{1,4}})
        {space_pattern}*$
        """,
        re.VERBOSE | re.MULTILINE,
    )

    pages_to_scan = min(10, len(doc))
    in_toc = False
    toc_end_page = 0

    for page_idx in range(pages_to_scan):
        page = doc[page_idx]
        text = page.get_text()
        lines = text.split('\n')

        for line in lines:
            line_stripped = line.strip()

            for pattern in toc_header_patterns:
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    in_toc = True
                    toc_end_page = page_idx + 3
                    break

            if in_toc and page_idx <= toc_end_page:
                match = toc_entry_pattern.match(line_stripped)
                if not match:
                    match = roman_pattern.match(line_stripped)

                if match:
                    num = match.group("num") or ""
                    title = match.group("title").strip()
                    page_num = int(match.group("page"))

                    level = 1
                    if num and '.' in num:
                        level = num.count('.') + 1

                    entries.append({
                        "level": level,
                        "title": f"{num} {title}".strip() if num else title,
                        "page": page_num,
                    })

            if in_toc and page_idx > toc_end_page and len(entries) > 3:
                break

        if in_toc and page_idx > toc_end_page and len(entries) > 3:
            break

    return entries


def _extract_toc_via_huridocs(pdf_path: Path) -> List[Dict[str, Any]]:
    """Extract TOC using HURIDOCS vision-based Docker service.

    Only runs when HURIDOCS_TOC_URL env var is set (e.g. http://localhost:5060).
    The service uses layout analysis to detect TOC pages visually.
    """
    if not _HURIDOCS_TOC_URL:
        return []

    try:
        import httpx
    except ImportError:
        logger.debug("httpx not available for HURIDOCS TOC fallback")
        return []

    endpoint = f"{_HURIDOCS_TOC_URL.rstrip('/')}/toc"

    try:
        with open(pdf_path, "rb") as f:
            files = {"file": (pdf_path.name, f, "application/pdf")}
            data = {}
            if _HURIDOCS_TOC_FAST:
                data["fast"] = "true"

            with httpx.Client(timeout=_HURIDOCS_TOC_TIMEOUT) as client:
                resp = client.post(endpoint, files=files, data=data)

        if resp.status_code != 200:
            logger.debug(f"HURIDOCS TOC returned {resp.status_code}")
            return []

        raw_entries = resp.json()
        if not isinstance(raw_entries, list) or not raw_entries:
            return []

        entries: List[Dict[str, Any]] = []
        for item in raw_entries:
            label = (item.get("label") or "").strip()
            if not label:
                continue

            level = (item.get("indentation", 0) or 0) + 1

            page = 0
            bbox = item.get("bounding_box")
            if bbox and isinstance(bbox, dict):
                page = int(bbox.get("page", 0) or 0)
            else:
                rects = item.get("selectionRectangles", [])
                if rects and isinstance(rects, list):
                    page = int(rects[0].get("page", 0) or 0)

            entries.append({"level": level, "title": label, "page": page})

        if entries:
            logger.info(
                f"HURIDOCS vision detected {len(entries)} TOC entries "
                f"(fast={_HURIDOCS_TOC_FAST})"
            )

        return entries

    except Exception as e:
        logger.debug(f"HURIDOCS TOC fallback failed: {e}")
        return []
