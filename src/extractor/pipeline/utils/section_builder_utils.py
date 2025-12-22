#!/usr/bin/env python3
"""Pure helpers for Stage 04 (Section Builder).

This module intentionally stays import‑light and side‑effect free so both
pipeline steps and external tools (e.g., DevOps scripts) can reuse small
deterministic helpers without pulling in Stage code.
"""
from __future__ import annotations

from extractor.pipeline.utils.reliability import log_stage_error
from typing import Tuple, Dict, Any, Optional, Iterable, List
import os
import re as _re

# Keep a conservative copy of the PDF font threshold used in Stage 04.
# Do not import from the step module to avoid cyclic deps.
PDF_LARGE_FONT_THRESHOLD: float = 14.0

def get_pdf_large_font_threshold() -> float:
    """Return the large-font threshold for PDF header detection.

    Env override: SPARTA_PDF_FONT_LARGE (float, e.g., 14.0)
    """
    try:
        v = os.getenv("SPARTA_PDF_FONT_LARGE")
        if v is None:
            return PDF_LARGE_FONT_THRESHOLD
        return float(v)
    except Exception as exc:
        log_stage_error('section_builder_utils.py', exc, {'context': 'section_builder_utils.py'})
        raise
        return PDF_LARGE_FONT_THRESHOLD


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
        log_stage_error('section_builder_utils.py', exc, {'context': 'section_builder_utils.py'})
        raise
        page = 0

    bbox = block.get("bbox") or []
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        try:
            x0 = float(bbox[0])
            y0 = float(bbox[1])
        except Exception as exc:
            log_stage_error('section_builder_utils.py', exc, {'context': 'section_builder_utils.py'})
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
        log_stage_error('section_builder_utils.py', exc, {'context': 'section_builder_utils.py'})
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
        log_stage_error('section_builder_utils.py', exc, {'context': 'section_builder_utils.py'})
        raise
        return "#000000"


def _bucket_color(hex_str: str) -> str:
    try:
        h = hex_str.lstrip('#')
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
        log_stage_error('section_builder_utils.py', exc, {'context': 'section_builder_utils.py'})
        raise
        return "unknown"


def _roman_to_int(roman: str) -> int:
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    roman = roman.upper()
    total = 0
    prev = 0
    for ch in reversed(roman):
        val = values.get(ch, 0)
        if val < prev:
            total -= val
        else:
            total += val
            prev = val
    return total


# -------------------------------
# Precompiled heading recognition
# -------------------------------
# Supports:
#  - Decimal paths: 1, 1.1, 1.2.3, 1.2.3.a
#  - Roman paths: IV, IV.2
#  - Alpha paths: A, A.1
#  - Parenthesized: (iv), 1)
#  - Labeled: Appendix/Annex/Section/Chapter/Part A.2 – Title
_RE_DECIMAL = _re.compile(
    r"""^\s*
        (?P<num>\d+(?:\.\d+)*(?:\.[a-z])?)
        \s*(?:[.:)\-–—])?\s+
        (?P<title>\S.*)$
    """,
    _re.IGNORECASE | _re.VERBOSE,
)
_RE_DECIMAL_PAREN = _re.compile(r"^\s*(?P<num>\d+)\)\s+(?P<title>\S.*)$")
_RE_ROMAN = _re.compile(
    r"""^\s*
        (?P<num>[IVXLCDM]+(?:\.[IVXLCDM]+)*)
        \.?\s+(?P<title>\S.*)$
    """,
    _re.IGNORECASE | _re.VERBOSE,
)
_RE_ROMAN_PAREN = _re.compile(r"^\s*\((?P<num>[ivxlcdm]+)\)\s+(?P<title>\S.*)$", _re.IGNORECASE)
_RE_ALPHA = _re.compile(r"^\s*(?P<num>[A-Z](?:\.\d+)*)\.?\s+(?P<title>\S.*)$")
_RE_LABELED = _re.compile(
    r"""^\s*
        (?P<label>Appendix|Annex|Section|Chapter|Part)
        \s+(?P<num>[A-Za-z0-9IVXLCDM.]+)
        \s*(?:[:.\-–—])?\s+
        (?P<title>\S.*)$
    """,
    _re.IGNORECASE | _re.VERBOSE,
)


def _count_depth_from_num(num: str) -> int:
    if not num:
        return 1
    parts = [p for p in num.replace(")", "").split(".") if p]
    return max(1, len(parts))


# ------------------------------------------------------------
# PDF section‑header detection (text + optional font evidence)
# ------------------------------------------------------------

def pdf_analyze_section_numbering(text: str) -> Dict[str, Any]:
    """Lightweight numbering analysis mirroring Stage‑04 logic.

    Returns a dict with keys:
      - has_numbering (bool)
      - numbering_type (str)
      - depth_level (int)
      - number_confidence (float)
      - number_text (str)
      - title_text (str)
      - number_span (dict|None)  # {start, end} in original text
      - title_span (dict|None)   # {start, end} in original text (leading '. ' trimmed)
    """
    res: Dict[str, Any] = {
        "has_numbering": False,
        "numbering_type": "none",
        "depth_level": 0,
        "number_confidence": 0.0,
        "number_text": "",
        "title_text": (text or "").strip(),
        "number_span": None,
        "title_span": None,
    }
    t = (text or "").strip()
    if not t:
        return res

    for typ, pat in (
        ("decimal", _RE_DECIMAL),
        ("decimal_paren", _RE_DECIMAL_PAREN),
        ("roman_paren", _RE_ROMAN_PAREN),
        ("roman", _RE_ROMAN),
        ("alpha", _RE_ALPHA),
        ("labeled", _RE_LABELED),
    ):
        m = pat.match(t)
        if not m:
            continue
        res["has_numbering"] = True
        res["numbering_type"] = typ
        num_text = (m.groupdict().get("num") or "").strip()
        title_text = (m.groupdict().get("title") or "").strip()
        # Spans
        try:
            ns, ne = m.span("num")
        except Exception as exc:
            log_stage_error('section_builder_utils.py', exc, {'context': 'section_builder_utils.py'})
            raise
            ns, ne = (0, 0)
        if "title" in m.groupdict() and (m.group("title") or ""):
            ts, te = m.span("title")
        else:
            ts, te = (ne, len(t))
        # Normalize title leading separators
        while ts < len(t) and t[ts : ts + 1] in ".:–—-) ":
            ts += 1
        title_text = t[ts:te].strip()
        depth = _count_depth_from_num(num_text)
        if typ in ("decimal_paren", "roman_paren"):
            depth = max(1, depth)
        conf_map = {
            "decimal": 0.95,
            "decimal_paren": 0.90,
            "roman": 0.85,
            "roman_paren": 0.85,
            "alpha": 0.80,
            "labeled": 0.90,
        }
        res.update(
            number_confidence=conf_map.get(typ, 0.8),
            depth_level=depth,
            number_text=(num_text if num_text else (m.groupdict().get("label", "") + " " + m.groupdict().get("num", "")).strip()),
            title_text=title_text,
            number_span={"start": int(ns), "end": int(ne)} if ne else None,
            title_span={"start": int(ts), "end": int(te)},
        )
        return res
    return res


def pdf_extract_section_title(text: str) -> str:
    """Return title with any leading numbering removed."""
    t = (text or "").strip()
    if not t:
        return ""
    na = pdf_analyze_section_numbering(t)
    if na.get("has_numbering"):
        return (na.get("title_text") or "").strip().lstrip(". ").strip()
    # Fallback: strip simple dotted numbers
    import re as _re
    m = _re.match(r"^\s*\d+(?:\.\d+)*\.?\s+(.*)$", t)
    return m.group(1).strip() if m else t


def is_probable_pdf_section_header(
    text: str,
    first_span_font: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Heuristic PDF section‑header detector for DevOps and pipeline callers.

    Inputs
    - text: raw block text from PDF OCR/layout
    - first_span_font: optional dict {size, bold, italic, color_bucket, name}

    Output
    - {
        is_header: bool,
        confidence: float,           # 0..1
        level: Optional[int],        # inferred; numbering depth or default 2
        title: str,                  # numbering stripped
        numbering: { ... },          # from pdf_analyze_section_numbering
        reason: str                  # human‑readable summary
      }

    Deterministic, no I/O.
    """
    txt = (text or "").strip()
    na = pdf_analyze_section_numbering(txt)
    title = pdf_extract_section_title(txt)

    # Font evidence
    fs = first_span_font or {}
    try:
        size = float(fs.get("size")) if fs.get("size") is not None else None
    except Exception as exc:
        log_stage_error('section_builder_utils.py', exc, {'context': 'section_builder_utils.py'})
        raise
        size = None
    is_bold = bool(fs.get("bold"))

    # Hard negatives (only if not numbered) — relaxed, do not require trailing period
    is_caption = bool(_re.match(r"^\s*(Table|Figure|Exhibit|Listing)\s+\d+(?:[-–]\d+)?[.:]", txt, _re.IGNORECASE))
    short_colon = len(txt) <= 40 and txt.endswith(":")
    terminal_sentence = txt.endswith(".") or txt.endswith(";")
    ends_with_comma = txt.endswith(",")
    multi_sentence = len(_re.findall(r"[\.!?]\s+\w", txt)) >= 2
    has_parens = ("(" in txt and ")" in txt)
    single_word = len(txt.split()) == 1
    short_all_caps = len(txt) < 10 and txt.isupper()
    too_long_line = len(txt) > 180

    # Positive textual patterns (when not numbered)
    formal_prefix = bool(_re.match(r"^(Chapter|Section|Part|Article|Appendix|Annex|Module|Unit)\s+[\dIVXLCDM]+", txt, _re.IGNORECASE))
    roman_start = bool(_re.match(r"^[IVXLCDM]+\.?\s+\w+", txt))
    letter_section = bool(_re.match(r"^[A-Z](?:\.\d+)*\.?\s+\w+", txt))

    words = txt.split()
    title_case_ratio = (sum(1 for w in words if w[:1].isupper()) / max(1, len(words))) if words else 0.0
    title_case_like = 2 <= len(words) <= 15 and title_case_ratio >= 0.7
    all_caps_medium = txt.isupper() and 5 <= len(txt) <= 60

    # Scoring
    confidence = 0.0
    reasons = []
    level: Optional[int] = None

    if na.get("has_numbering"):
        confidence = max(confidence, 0.9)
        reasons.append("numbering")
        level = int(na.get("depth_level") or 1)
    # Bold + large font is strong evidence
    if is_bold and (size or 0) >= get_pdf_large_font_threshold():
        confidence = max(confidence, 0.75)
        reasons.append("bold_large_font")

    # Valid header titles catalogue (exact/fuzzy)
    _VALID_HEADERS: set[str] = {
        "Acronyms", "Definitions", "Glossary", "References", "Notes", "Abbreviations",
        "Terms", "Symbols", "Conventions", "Notation", "Bibliography", "Appendix",
        "Index", "Abstract", "Summary", "Introduction", "Conclusion", "Methods",
        "Results", "Discussion", "Acknowledgments", "Acknowledgements", "Preface",
        "Foreword", "Contents"
    }
    tl = title.strip().lower()
    if tl and any(tl == v.lower() for v in _VALID_HEADERS):
        confidence = max(confidence, 0.7)
        reasons.append("valid_header_keyword")
    elif tl and _fuzzy_in_set(title, (h.lower() for h in _VALID_HEADERS), threshold=92.0):
        confidence = max(confidence, 0.65)
        reasons.append("valid_header_keyword_fuzzy")

    # Apply negatives if not numbered
    if not na.get("has_numbering"):
        if is_caption:
            confidence = min(confidence, 0.05)
            reasons.append("caption_negative")
        if terminal_sentence:
            confidence = min(confidence, 0.10)
            reasons.append("sentence_negative")
        if short_colon:
            confidence = min(confidence, 0.10)
            reasons.append("short_colon_negative")
        if ends_with_comma:
            confidence = min(confidence, 0.05)
            reasons.append("trailing_comma_negative")
        if multi_sentence:
            confidence = min(confidence, 0.01)
            reasons.append("multi_sentence_negative")
        if has_parens:
            confidence = min(confidence, 0.35)
            reasons.append("parentheses_negative")
        if single_word and not any(ch.isdigit() for ch in txt):
            confidence = min(confidence, 0.3)
            reasons.append("single_word_negative")
        if short_all_caps:
            confidence = min(confidence, 0.25)
            reasons.append("short_all_caps_negative")

        # Positive textual boosters (when not numbered)
        if formal_prefix:
            confidence = max(confidence, 0.85)
            reasons.append("formal_prefix")
        if roman_start:
            confidence = max(confidence, 0.7)
            reasons.append("roman_start")
        if letter_section:
            confidence = max(confidence, 0.6)
            reasons.append("letter_section")
        if title_case_like:
            confidence = max(confidence, 0.55)
            reasons.append("title_case_like")
        if all_caps_medium:
            confidence = max(confidence, 0.55)
            reasons.append("all_caps_medium")
        if too_long_line:
            confidence = min(confidence, 0.25)
            reasons.append("too_long")

    # Default level if still None
    if level is None:
        level = int(na.get("depth_level") or 2) if confidence >= 0.5 else None

    is_header = confidence >= 0.5

    spans = {"number": na.get("number_span"), "title": na.get("title_span")}

    return {
        "is_header": bool(is_header),
        "confidence": float(round(confidence, 3)),
        "level": level,
        "title": title,
        "numbering": na,
        "reason": ",".join(reasons) or ("low_confidence" if not is_header else "heuristic"),
        "spans": spans,
    }


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
        "reason": ",".join(reason_parts) if reason_parts else ("unknown" if is_header else "not_heading"),
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
    log_stage_error('section_builder_utils.py', exc, {'context': 'section_builder_utils.py'})
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


def filter_header_candidate(line_text: str, first_span_font: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Precision filter for a single candidate line.

    Wraps is_probable_pdf_section_header, returning the same dict but adding
    'candidate': True and echoing the original line.
    """
    res = is_probable_pdf_section_header(line_text, first_span_font)
    res["candidate"] = True
    res["raw_line"] = line_text
    return res
