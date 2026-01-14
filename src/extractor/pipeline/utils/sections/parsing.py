#! /usr/bin/env python3
"""Section parsing utilities for Stage 04 (Section Builder).

Handles numbering analysis, title extraction, and depth detection.
Delegates core heuristics to .heuristics module.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from extractor.pipeline.utils.sections.heuristics import (
    analyze_section_numbering as _analyze_section_numbering,
    extract_section_title as _extract_section_title,
    looks_like_header_text as _looks_like_header_text,
    _roman_to_int as _heuristic_roman_to_int,
)

# Re-export for compatibility
SECTION_NUMBER_PATTERNS = [
    r"^\d+\.\d+\.\d+\.\d+",
    r"^\d+\.\d+\.\d+",
    r"^\d+\.\d+",
    r"^\d+\.",
    r"^[A-Z]\.",
    r"^[a-z]\)",
    r"^\([ivxlcdm]+\)",
    r"^\d+\)",
]

def roman_to_int(roman: str) -> int:
    """Convert Roman numeral to integer."""
    # Simple implementation since the heuristic one is internal
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
    """Analyze section numbering patterns with depth detection."""
    return _analyze_section_numbering(text)

def derive_section_depth(numbering_analysis: Dict[str, Any]) -> List[int]:
    """Derive numeric section depth list from numbering analysis."""
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
        elif ntype in ("alpha_lower", "alpha"): # handle aliased types
            ch = re.sub(r"[^A-Za-z]", "", ntext).lower()[:1]
            if ch:
                depth = [ord(ch) - ord("a") + 1]
        elif ntype in ("roman", "roman_paren"):
            roman = re.sub(r"[^IVXLCDMivxlcdm]", "", ntext)
            if roman:
                depth = [roman_to_int(roman)]
    except Exception:
        depth = []
    return depth

def extract_section_title(text: str) -> str:
    """Extract title text without leading numbering."""
    return _extract_section_title(text)

def clean_section_title(text: str) -> str:
    """Remove SECTION_BREADCRUMB comments from title."""
    text_lines = text.split("\n")
    if len(text_lines) > 1 and "<!-- SECTION_BREADCRUMB" in text_lines[-1]:
        return text_lines[0].strip()
    return text.strip()

def detect_header_level(text: str) -> int:
    """Enhanced header level detection with depth analysis."""
    text = text.strip()
    if text.startswith("# "): return 1
    elif text.startswith("## "): return 2
    elif text.startswith("### "): return 3
    elif text.startswith("#### "): return 4
    elif text.startswith("##### "): return 5
    elif text.startswith("###### "): return 6
    
    numbering_analysis = analyze_section_numbering(text)
    if numbering_analysis["has_numbering"]:
        return numbering_analysis["depth_level"]
    
    # Fallback keyword detection
    lower_text = text.lower()
    if any(k in lower_text for k in ["introduction", "abstract", "conclusion", "references", "appendix"]): return 1
    if any(k in lower_text for k in ["methodology", "implementation", "results", "discussion"]): return 2
    if any(k in lower_text for k in ["interface", "protocol", "algorithm", "structure"]): return 3
    return 2

def looks_like_header_text(text: str) -> bool:
    """Heuristic: detect if text looks like a header."""
    return _looks_like_header_text(text)

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
