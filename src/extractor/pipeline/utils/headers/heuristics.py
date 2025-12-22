#!/usr/bin/env python3
"""Header heuristics for Stage 03 (Suspicious Header Verification).

Centralizes auto-accept and auto-reject logic to eliminate duplication
between the LLM path and skip_llm mode.
"""

from __future__ import annotations

import re
from typing import Any, Tuple


def normalize_header_text(text: str) -> str:
    """Normalize header text for comparison/matching.
    
    - Lowercases, strips whitespace
    - Removes leading numbering like "4.1.2" or "(iv)" or "a)"
    """
    s = (text or "").strip().lower()
    s = " ".join(s.split())  # collapse whitespace
    # Strip leading numbering
    s = re.sub(r"^(\(?[ivx]+\)|\d+(?:[\.-]\d+)*|[a-z]\)|[a-z]\.)\s+", "", s)
    return s


def font_signature(block: dict[str, Any]) -> str:
    """Build a font signature string from first_span_font.
    
    Format: name|size|bi|color (e.g., "Arial|12.0|b|black")
    """
    fs = block.get("first_span_font") or {}
    name = str(fs.get("name") or "?")
    size = fs.get("size")
    size_str = f"{float(size):.1f}" if isinstance(size, (int, float)) else str(size or "?")
    bold = "b" if fs.get("bold") else "n"
    italic = "i" if fs.get("italic") else "n"
    color = str(fs.get("color_bucket") or "?")
    return f"{name}|{size_str}|{bold}{italic}|{color}"


def analyze_header_heuristics(
    raw_text: str,
    first_span_font: dict[str, Any] | None = None,
) -> Tuple[str, str]:
    """Analyze text to determine if it should be auto-accepted/rejected as a header.
    
    Args:
        raw_text: The raw text content of the block
        first_span_font: Optional font info for additional signals
        
    Returns:
        Tuple of (verdict, reason_code) where:
        - verdict: "accept", "reject", or "llm" (needs LLM verification)
        - reason_code: explanation for the verdict
    """
    text = (raw_text or "").strip()
    if not text:
        return ("reject", "empty_text")
    
    # Check if numbered heading like "1.1.1 Title"
    is_numbered = bool(re.match(r"^\s*\d+(?:[\.-]\d+){1,}\s+\S", text))
    
    # If numbered with title after, likely a valid header
    if is_numbered:
        return ("accept", "numbered_heading")
    
    # Short colon label <= 40 chars ending with ":" - likely a wrapper label, not header
    if len(text) <= 40 and text.endswith(":"):
        return ("reject", "short_colon_label")
    
    # Bullet prefix detection (•, ●, ▪, ‣, ⁃, –, —, -, *, +, ·)
    bullet_chars = ("•", "●", "▪", "‣", "⁃", "–", "—", "-", "*", "+", "·")
    if any(text.startswith(c) for c in bullet_chars):
        return ("reject", "bullet_prefix")
    
    # Caption patterns: "Table N[.M][.:]" or "Figure N[.M][.:]"
    if re.match(r"^\s*(Table|Figure)\s+\d+(?:[-–.]\d+)?[.:]", text, re.IGNORECASE):
        return ("reject", "caption_pattern")
    
    # Sentence-like endings (. or ;) rarely are section headers
    if text.endswith(".") or text.endswith(";"):
        return ("reject", "terminal_punctuation")
    
    # "(continued)" or "- continued" patterns
    if re.search(r"\(continued\)|\s-\s*continued", text, re.IGNORECASE):
        return ("reject", "continued_pattern")
    
    # If no strong signal either way, defer to LLM
    return ("llm", "no_strong_heuristic")


def is_relevant_for_stage03(annotation: dict[str, Any]) -> bool:
    """Check if an annotation is marked as relevant for Stage 03."""
    try:
        return "03" in (annotation.get("relevant_to") or [])
    except Exception:
        return False


__all__ = [
    "normalize_header_text",
    "font_signature",
    "analyze_header_heuristics",
    "is_relevant_for_stage03",
]
