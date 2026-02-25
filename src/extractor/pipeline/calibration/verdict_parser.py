"""Natural language verdict parser for calibration feedback.

Parses human feedback like "that's a figure" into structured verdicts.
"""

import re
from dataclasses import dataclass
from typing import Any

from extractor.pipeline.calibration.models import HumanVerdict


@dataclass
class VerdictParseResult:
    """Result of parsing a natural language verdict."""

    verdict: HumanVerdict
    correction: dict[str, Any] | None = None
    note: str | None = None


# Element types we recognize
ELEMENT_TYPES = {"header", "table", "figure"}

# Patterns for each verdict type
CORRECT_PATTERNS = [
    r"^correct\b",
    r"^yes\b",
    r"^yep\b",
    r"^good\b",
    r"^looks?\s+good",
    r"^that'?s?\s+right",
    r"^right\b",
    r"^ok\b",
    r"^okay\b",
]

NOT_ELEMENT_PATTERNS = [
    r"not\s+an?\s+element",
    r"not\s+a?\s+real\s+element",
    r"^ignore\b",
    r"false\s+positive",
    r"just\s+(body\s+)?text",
    r"(just|only)\s+emphasis",
    r"that'?s?\s+not\s+an?\s+element",
    r"this\s+is\s+\w+,?\s+not\s+a",  # "this is emphasis, not a header"
]

SPLIT_PATTERNS = [
    r"split\s+(this|it|into)",
    r"two\s+elements",
    r"multiple\s+elements",
    r"should\s+be\s+split",
    r"^split\b",
]

FLAGGED_PATTERNS = [
    r"^flag\b",
    r"^unsure\b",
    r"not\s+sure",
    r"i'?m?\s+not\s+sure",
    r"ask\s+expert",
    r"need\s+help",
    r"flag\s+for\s+review",
    r"come\s+back",
]

ADJUST_BBOX_PATTERNS = [
    r"adjust\s+bbox",
    r"bbox\s+is\s+too",
    r"^too\s+(small|big|large)\b",
    r"extend\s+(the\s+)?bbox",
    r"bbox\s+cuts?\s+off",
    r"include\s+(the\s+)?caption",
    r"cutting\s+off",
]

# Patterns for extracting element type from wrong_type feedback
WRONG_TYPE_PATTERNS = [
    r"that'?s?\s+a\s+(\w+)",
    r"it'?s?\s+a\s+(\w+)",
    r"actually\s+a\s+(\w+)",
    r"should\s+be\s+(\w+)",
    r"wrong.*?(\w+)$",
]


def parse_verdict(text: str) -> VerdictParseResult:
    """Parse natural language feedback into a structured verdict.

    Args:
        text: Human feedback text (e.g., "that's a figure", "correct", "split this")

    Returns:
        VerdictParseResult with verdict type, optional correction, and optional note.
    """
    if not text or not text.strip():
        return VerdictParseResult(verdict=HumanVerdict.FLAGGED)

    text_lower = text.strip().lower()
    original_text = text.strip()

    # Extract note from various patterns
    note = _extract_note(original_text)

    # Check for ADJUST_BBOX first (specific phrases)
    for pattern in ADJUST_BBOX_PATTERNS:
        if re.search(pattern, text_lower):
            return VerdictParseResult(
                verdict=HumanVerdict.ADJUST_BBOX,
                note=note,
            )

    # Check for CORRECT
    for pattern in CORRECT_PATTERNS:
        if re.search(pattern, text_lower):
            return VerdictParseResult(
                verdict=HumanVerdict.CORRECT,
                note=note,
            )

    # Check for NOT_ELEMENT
    for pattern in NOT_ELEMENT_PATTERNS:
        if re.search(pattern, text_lower):
            return VerdictParseResult(
                verdict=HumanVerdict.NOT_ELEMENT,
                note=note,
            )

    # Check for SPLIT
    for pattern in SPLIT_PATTERNS:
        if re.search(pattern, text_lower):
            return VerdictParseResult(
                verdict=HumanVerdict.SPLIT,
                note=note,
            )

    # Check for FLAGGED
    for pattern in FLAGGED_PATTERNS:
        if re.search(pattern, text_lower):
            return VerdictParseResult(
                verdict=HumanVerdict.FLAGGED,
                note=note,
            )

    # Check for WRONG_TYPE with element type extraction
    element_type = _extract_element_type(text_lower)
    if element_type:
        return VerdictParseResult(
            verdict=HumanVerdict.WRONG_TYPE,
            correction={"correct_type": element_type},
            note=note,
        )

    # Check for explicit "wrong" without a type
    if re.search(r"\bwrong\b", text_lower):
        return VerdictParseResult(
            verdict=HumanVerdict.WRONG_TYPE,
            correction=None,
            note=note or original_text,
        )

    # Default to FLAGGED for ambiguous input
    return VerdictParseResult(
        verdict=HumanVerdict.FLAGGED,
        note=note or original_text,
    )


def _extract_element_type(text: str) -> str | None:
    """Extract element type from text like 'that's a figure'.

    Args:
        text: Lowercase text to extract from.

    Returns:
        Element type if found (header, table, figure), None otherwise.
    """
    for pattern in WRONG_TYPE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            candidate = match.group(1).lower()
            # Check if it's a known element type
            if candidate in ELEMENT_TYPES:
                return candidate
            # Handle plurals and variations
            if candidate.rstrip("s") in ELEMENT_TYPES:
                return candidate.rstrip("s")

    # Also check for element types mentioned anywhere
    for elem_type in ELEMENT_TYPES:
        if elem_type in text:
            # Make sure it's in a context suggesting it's the correct type
            if any(
                indicator in text for indicator in ["it's a", "that's a", "actually a", "should be"]
            ):
                return elem_type

    return None


def _extract_note(text: str) -> str | None:
    """Extract explanatory note from feedback text.

    Looks for notes after:
    - Dashes: "wrong - it's a wiring diagram"
    - Parentheses: "correct (but bbox is off)"
    - Because: "not an element because it's emphasis"

    Args:
        text: Original feedback text.

    Returns:
        Extracted note or None.
    """
    # Check for dash-separated note
    if " - " in text:
        parts = text.split(" - ", 1)
        if len(parts) > 1:
            return parts[1].strip()

    # Check for parenthetical note
    paren_match = re.search(r"\(([^)]+)\)", text)
    if paren_match:
        return paren_match.group(1).strip()

    # Check for "because" note
    because_match = re.search(r"\bbecause\s+(.+)$", text, re.IGNORECASE)
    if because_match:
        return because_match.group(1).strip()

    return None
