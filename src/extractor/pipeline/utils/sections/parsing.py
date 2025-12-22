#!/usr/bin/env python3
"""Section parsing utilities for Stage 04 (Section Builder).

Handles numbering analysis, title extraction, and depth detection.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# Section numbering patterns
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
    """Convert Roman numeral to integer."""
    values = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
    roman = roman.lower()
    result = 0
    prev = 0
    for char in reversed(roman):
        val = values.get(char, 0)
        if val < prev:
            result -= val
        else:
            result += val
        prev = val
    return result


def analyze_section_numbering(text: str) -> Dict[str, Any]:
    """Analyze section numbering patterns with depth detection."""
    text = (text or "").strip()
    if not text:
        return {"has_numbering": False}
    
    result: Dict[str, Any] = {"has_numbering": False, "raw_text": text}
    
    # Try each pattern
    for pattern in SECTION_NUMBER_PATTERNS:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            number_text = match.group(0)
            result["has_numbering"] = True
            result["number_text"] = number_text
            result["pattern"] = pattern
            
            # Detect type
            if re.match(r"^\d+(\.\d+)+", number_text):
                result["type"] = "decimal_multi"
                parts = [int(p) for p in number_text.rstrip(".").split(".") if p.isdigit()]
                result["depth"] = len(parts)
                result["parts"] = parts
            elif re.match(r"^\d+\.$", number_text):
                result["type"] = "decimal_single"
                result["depth"] = 1
                result["parts"] = [int(number_text.rstrip("."))]
            elif re.match(r"^[A-Z]\.$", number_text):
                result["type"] = "alpha_upper"
                result["depth"] = 1
                result["parts"] = [ord(number_text[0]) - ord("A") + 1]
            elif re.match(r"^[a-z]\)$", number_text):
                result["type"] = "alpha_lower_paren"
                result["depth"] = 2
                result["parts"] = [ord(number_text[0]) - ord("a") + 1]
            elif re.match(r"^\([ivxlcdm]+\)$", number_text, re.IGNORECASE):
                result["type"] = "roman"
                roman_num = number_text[1:-1]
                result["depth"] = 2
                result["parts"] = [roman_to_int(roman_num)]
            elif re.match(r"^\d+\)$", number_text):
                result["type"] = "decimal_paren"
                result["depth"] = 2
                result["parts"] = [int(number_text.rstrip(")"))]
            break
    
    return result


def derive_section_depth(numbering_analysis: Dict[str, Any]) -> List[int]:
    """Derive numeric section depth list from numbering analysis."""
    if not numbering_analysis.get("has_numbering"):
        return []
    return numbering_analysis.get("parts", [])


def extract_section_title(text: str) -> str:
    """Extract title text without leading numbering."""
    text = (text or "").strip()
    if not text:
        return ""
    
    # Remove leading numbering patterns
    for pattern in SECTION_NUMBER_PATTERNS:
        text = re.sub(f"^{pattern}\\s*", "", text, flags=re.IGNORECASE)
    
    return text.strip()


def clean_section_title(text: str) -> str:
    """Remove SECTION_BREADCRUMB comments from title."""
    text = (text or "").strip()
    # Remove breadcrumb markers
    text = re.sub(r"\s*<!--\s*SECTION_BREADCRUMB:.*?-->\s*", "", text)
    return text.strip()


def detect_header_level(text: str) -> int:
    """Enhanced header level detection with depth analysis."""
    analysis = analyze_section_numbering(text)
    if analysis.get("has_numbering"):
        depth = analysis.get("depth", 1)
        return min(depth, 6)  # Cap at 6 levels
    return 1


def looks_like_header_text(text: str) -> bool:
    """Heuristic: detect if text looks like a header."""
    text = (text or "").strip()
    if not text:
        return False
    
    # Accept numbered headings
    analysis = analyze_section_numbering(text)
    if analysis.get("has_numbering"):
        return True
    
    # Reject sentences (ending with punctuation)
    if text.endswith(".") or text.endswith(";") or text.endswith(","):
        words = text.split()
        if len(words) > 6:  # Long sentence
            return False
    
    # Short, non-sentence text is likely a header
    return len(text) < 80


def normalize_section_number(text: str) -> str:
    """Normalize a section number string."""
    analysis = analyze_section_numbering(text)
    if analysis.get("parts"):
        return ".".join(str(p) for p in analysis["parts"])
    return ""


def derive_parent_number(section_number: str) -> Optional[str]:
    """Derive parent section number from a child section number."""
    parts = section_number.split(".")
    if len(parts) > 1:
        return ".".join(parts[:-1])
    return None


__all__ = [
    "SECTION_NUMBER_PATTERNS",
    "roman_to_int",
    "analyze_section_numbering",
    "derive_section_depth",
    "extract_section_title",
    "clean_section_title",
    "detect_header_level",
    "looks_like_header_text",
    "normalize_section_number",
    "derive_parent_number",
]
