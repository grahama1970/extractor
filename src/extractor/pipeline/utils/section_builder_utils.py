#!/usr/bin/env python3
"""Pure helpers for Stage 04 (Section Builder).

This module intentionally stays import‑light and side‑effect free so both
pipeline steps and external tools (e.g., DevOps scripts) can reuse small
deterministic helpers without pulling in Stage code.
"""
from __future__ import annotations

from typing import Tuple, Dict, Any, Optional

# Keep a conservative copy of the PDF font threshold used in Stage 04.
# Do not import from the step module to avoid cyclic deps.
PDF_LARGE_FONT_THRESHOLD: float = 14.0


def _rgb_to_hex(rgb: Tuple[float, float, float]) -> str:
    try:
        r, g, b = rgb
        r = int(max(0, min(255, round(r * (255 if r <= 1 else 1)))))
        g = int(max(0, min(255, round(g * (255 if g <= 1 else 1)))))
        b = int(max(0, min(255, round(b * (255 if b <= 1 else 1)))))
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
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
    except Exception:
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

    import re as _re

    patterns = [
        (r"^(?:\d+\.){3}\d+", ("decimal", 4)),  # 1.1.1.1
        (r"^(?:\d+\.){2}\d+", ("decimal", 3)),  # 1.1.1
        (r"^(?:\d+\.)\d+", ("decimal", 2)),     # 1.1
        (r"^(\d+\.)", ("decimal", 1)),           # 1.
        (r"^[A-Z]\.", ("alpha_upper", 1)),
        (r"^[a-z]\)", ("alpha_lower", 2)),
        (r"^\([ivxlcdm]+\)", ("roman", 3)),
        (r"^(\d+)\)", ("decimal_paren", 1)),
    ]
    for pat, (typ, depth) in patterns:
        m = _re.match(pat, t)
        if m:
            res["has_numbering"] = True
            res["numbering_type"] = typ
            res["depth_level"] = depth
            res["number_confidence"] = 0.9
            num_text = m.group(0)
            res["number_text"] = num_text
            # Compute spans
            num_start, num_end = m.span(0)
            title_start = num_end
            # Trim leading '. ' from title span to align with displayed title
            while title_start < len(t) and t[title_start] in ('.', ' '):
                title_start += 1
            res["number_span"] = {"start": int(num_start), "end": int(num_end)}
            res["title_span"] = {"start": int(title_start), "end": int(len(t))}
            res["title_text"] = t[title_start:].strip()
            break
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
    except Exception:
        size = None
    is_bold = bool(fs.get("bold"))

    # Hard negatives (only if not numbered)
    import re as _re
    is_caption = bool(_re.match(r"^\s*(Table|Figure)\s+\d+(?:[-–]\d+)?[.:]", txt, _re.IGNORECASE))
    short_colon = len(txt) <= 40 and txt.endswith(":")
    terminal_sentence = txt.endswith(".") or txt.endswith(";")

    # Scoring
    confidence = 0.0
    reasons = []
    level: Optional[int] = None

    if na.get("has_numbering"):
        confidence = max(confidence, 0.9)
        reasons.append("numbering")
        level = int(na.get("depth_level") or 1)
    # Bold + large font is strong evidence
    if is_bold and (size or 0) >= PDF_LARGE_FONT_THRESHOLD:
        confidence = max(confidence, 0.75)
        reasons.append("bold_large_font")

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

    # Default level if still None
    if level is None:
        level = 2 if confidence >= 0.5 else None

    is_header = confidence >= 0.5

    spans = {
        "number": na.get("number_span"),
        "title": na.get("title_span"),
    }

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

    # Boilerplate filters (common site sections)
    tl = title.strip().lower()
    boilerplate_set = {
        "table of contents",
        "contents",
        "about the author",
        "acknowledgments",
        "acknowledgements",
        "references",
        "footer",
        "navigation",
    }
    is_boilerplate = tl in boilerplate_set
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
