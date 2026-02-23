"""Section heuristics and detection logic (Unified).

Refactored from section_builder_utils.py to eliminate split-brain logic.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Iterable, Tuple
from extractor.pipeline.utils.reliability import log_stage_error

# -------------------------------
# Constants & Regexes
# -------------------------------

# PDF font threshold
PDF_LARGE_FONT_THRESHOLD: float = 14.0

def get_pdf_large_font_threshold() -> float:
    import os
    try:
        v = os.getenv("SPARTA_PDF_FONT_LARGE")
        if v is None:
            return PDF_LARGE_FONT_THRESHOLD
        return float(v)
    except Exception:
        return PDF_LARGE_FONT_THRESHOLD

# Precompiled heading recognition
# FIX (sparta_f98d68e9): Use alternation to avoid greedy \s* consuming space
# Now matches both "1. Introduction" and "1 Introduction"
_RE_DECIMAL = re.compile(
    r"""^\s*
        (?P<num>\d+(?:\.\d+)*(?:\.[a-z])?)
        (?:[.:)\-–—]\s*|\s+)
        (?P<title>\S.*)$
    """,
    re.IGNORECASE | re.VERBOSE,
)
_RE_DECIMAL_PAREN = re.compile(r"^\s*(?P<num>\d+)\)\s+(?P<title>\S.*)$")
# FIX: Require trailing dot for Roman to avoid words like 'ID', 'DIV', 'DIM'
_RE_ROMAN = re.compile(
    r"""^\s*
        (?P<num>[IVXLCDM]+(?:\.[IVXLCDM]+)*)
        \.\s+(?P<title>\S.*)$
    """,
    re.IGNORECASE | re.VERBOSE,
)
_RE_ROMAN_PAREN = re.compile(r"^\s*\((?P<num>[ivxlcdm]+)\)\s+(?P<title>\S.*)$", re.IGNORECASE)
# FIX: Require trailing dot for Alpha, and title must not start with =
_RE_ALPHA = re.compile(r"^\s*(?P<num>[A-Z](?:\.\d+)*)\.\s+(?P<title>[^=].*)$")
_RE_LABELED = re.compile(
    r"""^\s*
        (?P<label>Appendix|Annex|Section|Chapter|Part)
        \s+(?P<num>[A-Za-z0-9IVXLCDM.]+)
        \s*(?:[:.\-–—])?\s+
        (?P<title>\S.*)$
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Valid header titles catalogue (exact/fuzzy)
_VALID_HEADERS: set[str] = {
    "Acronyms", "Definitions", "Glossary", "References", "Notes", "Abbreviations",
    "Terms", "Symbols", "Conventions", "Notation", "Bibliography", "Appendix",
    "Index", "Abstract", "Summary", "Introduction", "Conclusion", "Methods",
    "Results", "Discussion", "Acknowledgments", "Acknowledgements", "Preface",
    "Foreword", "Contents", "Overview", "Background", "Requirements",
    "Specification", "Interface", "Architecture", "Design", "Implementation",
    "Analysis", "Validation", "Verification", "Testing", "Scope", "Purpose",
}

# -------------------------------
# Fuzzy Logic
# -------------------------------

try:
    from rapidfuzz import fuzz as _rf_fuzz
    _HAVE_RAPIDFUZZ = True
except ImportError:
    _HAVE_RAPIDFUZZ = False
import difflib as _difflib

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

def _similarity_ratio(a: str, b: str) -> float:
    a = a.strip().lower()
    b = b.strip().lower()
    if _HAVE_RAPIDFUZZ:
        return float(_rf_fuzz.token_set_ratio(a, b))
    return float(_difflib.SequenceMatcher(None, a, b).ratio() * 100.0)

def _fuzzy_in_set(title: str, candidates: Iterable[str], threshold: float = 92.0) -> bool:
    t = (title or "").strip().lower()
    if not t:
        return False
    for c in candidates:
        if _similarity_ratio(t, c) >= threshold:
            return True
    return False

# -------------------------------
# Analysis Functions
# -------------------------------

def _count_depth_from_num(num: str) -> int:
    if not num:
        return 1
    parts = [p for p in num.replace(")", "").split(".") if p]
    return max(1, len(parts))

def analyze_section_numbering(text: str) -> Dict[str, Any]:
    """Lightweight numbering analysis.
    
    Refactored from section_builder_utils.py.
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
        
        # Spans
        try:
            ns, ne = m.span("num")
        except Exception:
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

def extract_section_title(text: str) -> str:
    """Return title with any leading numbering removed."""
    t = (text or "").strip()
    if not t:
        return ""
    na = analyze_section_numbering(t)
    if na.get("has_numbering"):
        return (na.get("title_text") or "").strip().lstrip(". ").strip()
    m = re.match(r"^\s*\d+(?:\.\d+)*\.?\s+(.*)$", t)
    return m.group(1).strip() if m else t

def is_probable_pdf_section_header(
    text: str,
    first_span_font: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Heuristic PDF section-header detector (Unified)."""
    txt = (text or "").strip()
    na = analyze_section_numbering(txt)
    title = extract_section_title(txt)
    spans = {"number": na.get("number_span"), "title": na.get("title_span")}

    # Font evidence
    fs = first_span_font or {}
    try:
        size = float(fs.get("size")) if fs.get("size") is not None else None
    except Exception:
        size = None
    is_bold = bool(fs.get("bold"))

    # Hard negatives (only if not numbered) — relaxed, do not require trailing period
    # Allow colon, dot, OR parenthesis (e.g. "Table 1 (Continued)")
    is_caption = bool(re.match(r"^\s*(Table|Figure|Exhibit|Listing)\s+\d+(?:[-–]\d+)?(?:[.:]|\s*\()", txt, re.IGNORECASE))
    short_colon = len(txt) <= 40 and txt.endswith(":")
    terminal_sentence = txt.endswith(".") or txt.endswith(";")
    ends_with_comma = txt.endswith(",")
    multi_sentence = len(re.findall(r"[\.!?]\s+\w", txt)) >= 2
    has_parens = ("(" in txt and ")" in txt)
    single_word = len(txt.split()) == 1
    short_all_caps = len(txt) < 10 and txt.isupper()
    too_long_line = len(txt) > 180

    # Positive textual patterns
    formal_prefix = bool(re.match(r"^(Chapter|Section|Part|Article|Appendix|Annex|Module|Unit)\s+[\dIVXLCDM]+", txt, re.IGNORECASE))
    # FIX: Require dot for Roman start attempts to avoid false positives like "ID Value" or "A I"
    roman_start = bool(re.match(r"^[IVXLCDM]+\.\s+\w+", txt))
    letter_section = bool(re.match(r"^[A-Z](?:\.\d+)*\.?\s+\w+", txt))

    words = txt.split()
    title_case_ratio = (sum(1 for w in words if w[:1].isupper()) / max(1, len(words))) if words else 0.0
    title_case_like = 2 <= len(words) <= 15 and title_case_ratio >= 0.7
    # Data table rejection: ALL CAPS check requires no digits
    all_caps_medium = txt.isupper() and 5 <= len(txt) <= 60 and not re.search(r"\d", txt)

    # Negative: Requirement/Assertion patterns (Engineering docs)
    # Starts with "REQ-" or contains "shall" in a short sentence?
    # Usually we don't want these as Section Headers unless clearly numbered.
    is_requirement_id = bool(re.match(r"^\s*REQ-[\w-]+[:\s]", txt, re.IGNORECASE))
    
    # Scoring
    confidence = 0.0
    reasons = []
    level: Optional[int] = None

    if is_requirement_id:
        confidence = 0.0
        reasons.append("requirement_id_negative")
        # Force return low confidence immediately
        return {
            "is_header": False,
            "confidence": 0.0,
            "level": None,
            "title": title,
            "numbering": na,
            "reason": "requirement_id_negative",
            "spans": spans,
        }

    if na.get("has_numbering"):
        confidence = max(confidence, 0.9)
        reasons.append("numbering")
        level = int(na.get("depth_level") or 1)
        
    if is_bold and (size or 0) >= get_pdf_large_font_threshold():
        confidence = max(confidence, 0.75)
        reasons.append("bold_large_font")

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

        # Positive textual boosters
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
            confidence = max(confidence, 0.45)
            reasons.append("title_case_like")
        if all_caps_medium:
            confidence = max(confidence, 0.45)
            reasons.append("all_caps_medium")
        if too_long_line:
            confidence = min(confidence, 0.25)
            reasons.append("too_long")

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

def looks_like_header_text(text: str) -> bool:
    """Text-only heuristic wrapper (Legacy interface compatible)."""
    res = is_probable_pdf_section_header(text)
    return res["is_header"]
