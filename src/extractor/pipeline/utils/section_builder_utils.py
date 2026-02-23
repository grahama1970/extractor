#!/usr/bin/env python3
"""Pure helpers for Stage 04 (Section Builder).

This module intentionally stays import‑light and side‑effect free so both
pipeline steps and external tools (e.g., DevOps scripts) can reuse small
deterministic helpers without pulling in Stage code.
"""
from __future__ import annotations

from extractor.pipeline.utils.reliability import log_stage_error
from typing import Tuple, Dict, Any, Optional, Iterable, List
import re as _re

# Delegates to shared heuristics module
from extractor.pipeline.utils.sections.heuristics import (
    analyze_section_numbering as pdf_analyze_section_numbering,
    extract_section_title as pdf_extract_section_title,
    is_probable_pdf_section_header,
)


def canonical_block_order_key(block: Dict[str, Any]) -> Tuple[int, float, float, int]:
    """Canonical per-block sort key used across stages.

    Order priority:
      1) page index
      2) y0 (top coordinate)
      3) x0 (left coordinate)
      4) block_id (stable tiebreaker)

    The goal is to enforce a deterministic reading order that matches
    visual layout for all consumers (02, 04, 04a, 06b, 07, 09a, etc.).
    """
    try:
        raw_page = block.get("page")
        if raw_page is None:
            raw_page = block.get("page_idx", block.get("page_index", 0))
        page = int(raw_page)
    except Exception as exc:
        log_stage_error("section_builder_utils.py", exc, {"context": "section_builder_utils.py"})
        raise
        page = 0

    bbox = block.get("bbox") or []
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        try:
            x0 = float(bbox[0])
            y0 = float(bbox[1])
        except Exception as exc:
            log_stage_error(
                "section_builder_utils.py", exc, {"context": "section_builder_utils.py"}
            )
            raise
            x0 = 0.0
            y0 = 0.0
    else:
        # Sentinel: unknown geometry → push towards the end of the page.
        x0 = 0.0
        y0 = 1e9

    try:
        bid = int(block.get("block_id", 0))
    except Exception as exc:
        log_stage_error("section_builder_utils.py", exc, {"context": "section_builder_utils.py"})
        raise
        bid = 0

    return (page, y0, x0, bid)


def _rgb_to_hex(rgb: Tuple[float, float, float]) -> str:
    try:
        r, g, b = rgb
        r = int(max(0, min(255, round(r * (255 if r <= 1 else 1)))))
        g = int(max(0, min(255, round(g * (255 if g <= 1 else 1)))))
        b = int(max(0, min(255, round(b * (255 if b <= 1 else 1)))))
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception as exc:
        log_stage_error("section_builder_utils.py", exc, {"context": "section_builder_utils.py"})
        raise
        return "#000000"


def _bucket_color(hex_str: str) -> str:
    try:
        h = hex_str.lstrip("#")
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        if r < 30 and g < 30 and b < 30:
            return "black"
        if r > 200 and g > 200 and b > 200:
            return "white"
        if r > g and r > b:
            return "red"
        if g > r and g > b:
            return "green"
        if b > r and b > g:
            return "blue"
        return "gray"
    except Exception as exc:
        log_stage_error("section_builder_utils.py", exc, {"context": "section_builder_utils.py"})
        raise
        return "unknown"


# -------------------------------------
# HTML section‑header detection utility
# -------------------------------------


def html_heading_info(
    *,
    tag_name: Optional[str],
    text: str,
    role: Optional[str] = None,
    aria_level: Optional[int] = None,
) -> Dict[str, Any]:
    """Return normalized info for an HTML heading.

    Inputs
    - tag_name: e.g., 'h1'..'h6' (case‑insensitive) or None
    - text: heading innerText
    - role: optional ARIA role (e.g., 'heading')
    - aria_level: optional ARIA heading level

    Output keys
    - is_header (bool), confidence (float), level (int|None), title (numbering removed),
      numbering (dict), reason (str), is_boilerplate (bool)
    """
    t = (text or "").strip()
    tn = (tag_name or "").lower()
    rl = (role or "").lower()

    # Determine level from tag or ARIA
    level: Optional[int] = None
    reason_parts = []
    confidence = 0.0

    if tn.startswith("h") and len(tn) == 2 and tn[1].isdigit():
        level = int(tn[1])
        confidence = 0.95
        reason_parts.append("tag_h1_h6")
    elif rl == "heading" and aria_level:
        level = int(aria_level)
        confidence = 0.85
        reason_parts.append("role_heading_aria_level")
    elif rl == "heading":
        level = 2
        confidence = 0.6
        reason_parts.append("role_heading_default_level")

    # Numbering + title extraction (reuse PDF logic safely)
    na = pdf_analyze_section_numbering(t)
    title = pdf_extract_section_title(t)

    # Boilerplate filters (site/navigation/ancillary blocks), with fuzzy match
    is_boilerplate = _is_boilerplate_html_title(title)
    if is_boilerplate:
        reason_parts.append("boilerplate")

    is_header = level is not None
    return {
        "is_header": bool(is_header),
        "confidence": float(round(confidence, 3)) if is_header else 0.0,
        "level": level,
        "title": title,
        "numbering": na,
        "reason": (
            ",".join(reason_parts) if reason_parts else ("unknown" if is_header else "not_heading")
        ),
        "spans": {"number": na.get("number_span"), "title": na.get("title_span")},
        "is_boilerplate": is_boilerplate,
    }


# -----------------------------
# HTML boilerplate fuzzy filter
# -----------------------------

try:  # optional, fast path if installed
    from rapidfuzz import fuzz as _rf_fuzz  # type: ignore

    _HAVE_RAPIDFUZZ = True
except Exception as exc:
    log_stage_error("section_builder_utils.py", exc, {"context": "section_builder_utils.py"})
    raise
    _HAVE_RAPIDFUZZ = False
import difflib as _difflib  # fallback


_BOILERPLATE_TITLES: set[str] = {
    # TOC and variants
    "table of contents",
    "toc",
    "contents",
    # Site chrome
    "navigation",
    "site navigation",
    "main navigation",
    "primary navigation",
    "footer",
    "header",
    "sidebar",
    "sitemap",
    "breadcrumbs",
    "skip to content",
    "skip navigation",
    # Meta/legal
    "copyright",
    "legal",
    "license",
    "privacy policy",
    "cookie policy",
    "terms of service",
    "terms & conditions",
    # Social/engagement
    "share",
    "follow us",
    "newsletter",
    "subscribe",
    "comments",
    "leave a reply",
    # Author/about
    "about",
    "about us",
    "about the author",
    "author",
    "authors",
    "contact",
    "contact us",
    # Misc content we usually want to drop from section anchoring
    "acknowledgments",
    "acknowledgements",
    "related posts",
    "related articles",
    "tags",
    "advertisement",
    "sponsored",
}

_SHORT_NAV_TOKENS: set[str] = {
    "home",
    "menu",
    "search",
    "login",
    "log in",
    "sign in",
    "sign up",
    "next",
    "previous",
    "back",
}


def _similarity_ratio(a: str, b: str) -> float:
    a = a.strip().lower()
    b = b.strip().lower()
    if _HAVE_RAPIDFUZZ:
        # token_set ratio is robust to word order and dupes; returns 0..100
        return float(_rf_fuzz.token_set_ratio(a, b))
    # Fallback: difflib ratio scaled to 0..100
    return float(_difflib.SequenceMatcher(None, a, b).ratio() * 100.0)


def _fuzzy_in_set(title: str, candidates: Iterable[str], threshold: float = 90.0) -> bool:
    t = (title or "").strip().lower()
    if not t:
        return False
    for c in candidates:
        if _similarity_ratio(t, c) >= threshold:
            return True
    return False


def _is_boilerplate_html_title(title: str) -> bool:
    tl = (title or "").strip().lower()
    if not tl:
        return False
    # Exact short tokens
    if tl in _SHORT_NAV_TOKENS:
        return True
    # Exact set
    if tl in _BOILERPLATE_TITLES:
        return True
    # Common prefixes/suffixes (fast path)
    if tl.startswith("table of contents") or tl.endswith("navigation"):
        return True
    # Fuzzy match against catalog
    return _fuzzy_in_set(tl, _BOILERPLATE_TITLES, threshold=90.0)


# ---------------------------------------------
# Candidate pool (forgiving regex → Python filter)
# ---------------------------------------------


_CANDIDATE_PATTERNS: List[Tuple[str, _re.Pattern[str]]] = [
    (
        "numeric_prefix",
        _re.compile(r"^\s*\d+(?:[\.\-–—]\d+)*(?:\.[a-z])?\.?\s+\S", _re.IGNORECASE),
    ),
    (
        "formal_prefix",
        _re.compile(
            r"^\s*(Chapter|Section|Part|Article|Appendix|Annex|Module|Unit)\s+[A-Za-z0-9IVXLCDM.]+\b",
            _re.IGNORECASE,
        ),
    ),
    (
        "roman_start",
        _re.compile(r"^\s*[IVXLCDM]+\.?\s+\S", _re.IGNORECASE),
    ),
    (
        "lettered_start",
        _re.compile(r"^\s*[A-Z](?:\.\d+)*\.?\s+\S"),
    ),
    (
        "appendix_dash_colon",
        _re.compile(r"^\s*(Appendix|Annex)\s+[A-Za-z0-9.]+\s*(?:[:\-–—])\s+\S", _re.IGNORECASE),
    ),
]


def find_header_candidates_in_text(text: str) -> List[Dict[str, Any]]:
    """Scan multi-line text, return a forgiving candidate pool with absolute char spans.

    Returns a list of entries:
      {
        'line_index': int,
        'line_start': int,        # absolute char index of line start
        'line_end': int,          # absolute char index of line end (exclusive) including newline
        'pattern': str,           # which candidate pattern matched
        'raw_line': str,
        'number_span_abs': {start,end} | None,
        'title_span_abs': {start,end} | None,
        'number_text': str,
        'title_text': str,
      }
    """
    results: List[Dict[str, Any]] = []
    if not isinstance(text, str) or not text:
        return results

    offset = 0
    for idx, line in enumerate(text.splitlines(keepends=True)):
        line_no_nl = line.rstrip("\n")
        matched_name: Optional[str] = None
        for name, pat in _CANDIDATE_PATTERNS:
            if pat.match(line_no_nl):
                matched_name = name
                break
        if not matched_name:
            offset += len(line)
            continue

        # Compute number/title spans relative to the line, then convert to absolute
        na = pdf_analyze_section_numbering(line_no_nl)
        number_span = na.get("number_span")
        title_span = na.get("title_span")
        abs_num = (
            {"start": offset + number_span["start"], "end": offset + number_span["end"]}
            if number_span
            else None
        )
        abs_title = (
            {"start": offset + title_span["start"], "end": offset + title_span["end"]}
            if title_span
            else None
        )
        results.append(
            {
                "line_index": idx,
                "line_start": offset,
                "line_end": offset + len(line),
                "pattern": matched_name,
                "raw_line": line_no_nl,
                "number_span_abs": abs_num,
                "title_span_abs": abs_title,
                "number_text": na.get("number_text", ""),
                "title_text": na.get("title_text", line_no_nl.strip()),
            }
        )
        offset += len(line)

    return results


def filter_header_candidate(
    line_text: str, first_span_font: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Precision filter for a single candidate line.

    Wraps is_probable_pdf_section_header, returning the same dict but adding
    'candidate': True and echoing the original line.
    """
    res = is_probable_pdf_section_header(line_text, first_span_font)
    res["candidate"] = True
    res["raw_line"] = line_text
    return res
