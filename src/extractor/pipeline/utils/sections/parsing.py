#!/usr/bin/env python3
"""Section parsing utilities for Stage 04 (Section Builder).

Handles numbering analysis, title extraction, and depth detection.
Matches API contract from section_builder_utils_local (sbul).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from extractor.pipeline.utils.section_builder_utils import (
    _roman_to_int,
    pdf_analyze_section_numbering as _pdf_analyze_numbering,
)

# Section numbering patterns (match deepest first)
SECTION_NUMBER_PATTERNS = [
    r"^\d+\.\d+\.\d+\.\d+",  # 1.1.1.1
    r"^\d+\.\d+\.\d+",       # 1.1.1
    r"^\d+\.\d+",            # 1.1
    r"^\d+\.",               # 1.
    r"^[A-Z]\.",             # A.
    r"^[a-z]\)",             # a)
    r"^\([ivxlcdm]+\)",      # (i) (ii)
    r"^\d+\)",               # 1)
]


def roman_to_int(roman: str) -> int:
    """Convert Roman numeral to integer (delegates to shared impl)."""
    return _roman_to_int(roman)


def normalize_section_number(value: Optional[str]) -> str:
    """Normalize a section number string."""
    if not value:
        return ""
    return str(value).strip().rstrip(".")


def coerce_depth(depth: Any) -> List[int]:
    """Coerce depth to list of integers."""
    if isinstance(depth, list):
        normalized: List[int] = []
        for item in depth:
            try:
                normalized.append(int(item))
            except Exception:
                continue
        if normalized:
            return normalized
    return []


def derive_parent_number(sec_num: str) -> Optional[str]:
    """Derive parent section number from a child section number."""
    trimmed = normalize_section_number(sec_num)
    if not trimmed:
        return None
    parts = [p for p in trimmed.split(".") if p]
    if len(parts) <= 1:
        return None
    return ".".join(parts[:-1])


def analyze_section_numbering(text: str) -> Dict[str, Any]:
    """Analyze section numbering patterns with depth detection.
    
    Returns dict with keys:
        - has_numbering: bool
        - numbering_type: str ("decimal", "roman", "alpha_upper", etc.)
        - depth_level: int
        - number_confidence: float
        - number_text: str
        - title_text: str
    """
    t = (text or "").strip()
    if not t:
        return {
            "has_numbering": False,
            "numbering_type": "none",
            "depth_level": 0,
            "number_confidence": 0.0,
            "number_text": "",
            "title_text": "",
        }
    
    try:
        analysis = _pdf_analyze_numbering(t)
    except Exception:
        analysis = {
            "has_numbering": False,
            "numbering_type": "none",
            "depth_level": 0,
            "number_confidence": 0.0,
            "number_text": "",
            "title_text": t,
        }
    
    # Suppress lowercase roman numerals that are likely false positives
    num_text = analysis.get("number_text") or ""
    if analysis.get("numbering_type") == "roman" and num_text.islower():
        analysis.update(
            has_numbering=False,
            numbering_type="none",
            number_confidence=0.0,
            number_text="",
            depth_level=0,
        )
    
    # Ensure baseline keys always exist
    analysis.setdefault("title_text", t)
    analysis.setdefault("number_text", "")
    analysis.setdefault("depth_level", 0)
    analysis.setdefault("numbering_type", "none")
    analysis.setdefault("number_confidence", 0.0)
    analysis.setdefault("has_numbering", False)
    return analysis


def derive_section_depth(numbering_analysis: Dict[str, Any]) -> List[int]:
    """Derive numeric section depth list from numbering analysis.
    
    Examples:
    - number_text='4.1.5.4' -> [4,1,5,4]
    - number_text='1.' -> [1]
    - number_text='A.' with alpha_upper -> [1] (A=1, B=2, ...)
    - number_text='(iv)' with roman -> [4]
    - number_text='1)' with decimal_paren -> [1]
    """
    depth: List[int] = []
    if not numbering_analysis or not numbering_analysis.get("has_numbering"):
        return depth
    
    ntype = numbering_analysis.get("numbering_type")
    ntext = (numbering_analysis.get("number_text") or "").strip()
    if not ntext:
        return depth
    
    try:
        if ntype == "decimal":
            ntext = ntext.rstrip(".")
            parts = [p for p in ntext.split(".") if p]
            depth = [int(p) for p in parts]
        elif ntype == "decimal_paren":
            num = re.sub(r"[^0-9]", "", ntext)
            if num:
                depth = [int(num)]
        elif ntype == "alpha_upper":
            ch = re.sub(r"[^A-Za-z]", "", ntext).upper()[:1]
            if ch:
                depth = [ord(ch) - ord("A") + 1]
        elif ntype == "alpha_lower":
            ch = re.sub(r"[^A-Za-z]", "", ntext).lower()[:1]
            if ch:
                depth = [ord(ch) - ord("a") + 1]
        elif ntype == "roman":
            roman = re.sub(r"[^IVXLCDMivxlcdm]", "", ntext)
            if roman:
                depth = [_roman_to_int(roman)]
    except Exception:
        depth = []
    return depth


def extract_section_title(text: str) -> str:
    """Extract title text without leading numbering."""
    text = (text or "").strip()
    if not text:
        return ""
    
    na = analyze_section_numbering(text)
    if na.get("has_numbering"):
        title = na.get("title_text") or ""
        return title.strip().lstrip(". ").strip()
    
    # Fallback: strip single leading number + dot pattern
    m = re.match(r"^\s*\d+(?:\.\d+)*\.?\s+(.*)$", text)
    if m:
        return m.group(1).strip()
    return text


def clean_section_title(text: str) -> str:
    """Remove SECTION_BREADCRUMB comments from title."""
    text_lines = text.split("\n")
    if len(text_lines) > 1 and "<!-- SECTION_BREADCRUMB" in text_lines[-1]:
        return text_lines[0].strip()
    return text.strip()


def detect_header_level(text: str) -> int:
    """Enhanced header level detection with depth analysis."""
    text = text.strip()
    
    # Check for markdown-style headers first
    if text.startswith("# "):
        return 1
    elif text.startswith("## "):
        return 2
    elif text.startswith("### "):
        return 3
    elif text.startswith("#### "):
        return 4
    elif text.startswith("##### "):
        return 5
    elif text.startswith("###### "):
        return 6
    
    # Use numbering analysis
    numbering_analysis = analyze_section_numbering(text)
    if numbering_analysis["has_numbering"]:
        return numbering_analysis["depth_level"]
    
    # Fallback to keyword-based detection
    lower_text = text.lower()
    
    # Level 1 keywords
    if any(k in lower_text for k in ["introduction", "abstract", "conclusion", "references", "appendix"]):
        return 1
    
    # Level 2 keywords
    if any(k in lower_text for k in ["methodology", "implementation", "results", "discussion"]):
        return 2
    
    # Level 3 keywords
    if any(k in lower_text for k in ["interface", "protocol", "algorithm", "structure"]):
        return 3
    
    # Default to level 2
    return 2


def looks_like_header_text(text: str) -> bool:
    """Heuristic: detect if text looks like a header.
    
    Strategy: Cast wide regex net, then filter false positives with Python.
    Uses both exact and fuzzy matching against known header keywords.
    """
    t = (text or "").strip()
    if not t:
        return False
    
    # Known valid header titles (exact/fuzzy match)
    _VALID_HEADERS = {
        "Acronyms", "Definitions", "Glossary", "References", "Notes", "Abbreviations",
        "Terms", "Symbols", "Conventions", "Notation", "Bibliography", "Appendix",
        "Index", "Abstract", "Summary", "Introduction", "Conclusion", "Methods",
        "Results", "Discussion", "Acknowledgments", "Acknowledgements", "Preface",
        "Foreword", "Contents", "Overview", "Background", "Requirements",
        "Specification", "Interface", "Architecture", "Design", "Implementation",
        "Analysis", "Validation", "Verification", "Testing", "Scope", "Purpose",
    }
    
    # === CHECK 1: Exact/fuzzy match against known headers ===
    tl = t.strip().lower()
    # Exact match
    if any(tl == h.lower() for h in _VALID_HEADERS):
        return True
    # Fuzzy match (92% threshold)
    try:
        from rapidfuzz import fuzz
        for h in _VALID_HEADERS:
            if fuzz.ratio(tl, h.lower()) >= 92:
                return True
    except ImportError:
        pass
    
    # === CHECK 2: Wide regex net for numbered/formatted patterns ===
    numbered_patterns = [
        r"^\d+(?:\.\d+)*\.?\s+.+",      # 1., 1.2, 1.2.3, 1.2.3.4. with title
        r"^[A-Z]\.\s+.+",                # A. Title
        r"^[a-z]\)\s+.+",                # a) Title
        r"^\([ivxlcdmIVXLCDM]+\)\s+.+",  # (i), (ii), (IV) Title
        r"^\d+\)\s+.+",                  # 1) Title
    ]
    
    format_patterns = [
        r"^#+\s+.+",                     # Markdown headers
        r".+\(Simulated\)$",             # Test markers
    ]
    
    all_patterns = numbered_patterns + format_patterns
    
    for pattern in all_patterns:
        if re.match(pattern, t):
            # === FILTER FALSE POSITIVES ===
            if len(t) < 3:
                continue
            title_part = re.sub(r"^[\d\.\)\(\s]+", "", t).strip()
            if len(title_part) < 2:
                continue
            if t[0].islower() and not re.match(r"^[a-z]\)", t):
                continue
            return True
    
    # === CHECK 3: ALL CAPS multi-word (common for unnumbered headers) ===
    alpha = re.sub(r"[^A-Za-z]", "", t)
    if alpha and t.upper() == t and len(alpha) >= 6 and len(t.split()) >= 2:
        return True
    
    return False


__all__ = [
    "SECTION_NUMBER_PATTERNS",
    "roman_to_int",
    "normalize_section_number",
    "coerce_depth",
    "derive_parent_number",
    "analyze_section_numbering",
    "derive_section_depth",
    "extract_section_title",
    "clean_section_title",
    "detect_header_level",
    "looks_like_header_text",
]
