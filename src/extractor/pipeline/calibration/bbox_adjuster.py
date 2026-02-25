"""Bounding box adjustment for calibration feedback.

Parses human descriptions of bbox adjustments and applies them.
"""

import re
from dataclasses import dataclass
from enum import Enum


class AdjustmentType(str, Enum):
    """Type of bbox adjustment."""

    EXTEND = "extend"
    SHRINK = "shrink"
    ABSOLUTE = "absolute"
    SEMANTIC = "semantic"


@dataclass
class BboxAdjustment:
    """Parsed bbox adjustment."""

    adjustment_type: AdjustmentType
    direction: str | None = None  # left, right, top, bottom, width
    amount: int | None = None
    new_bbox: list[float] | None = None


# Patterns for parsing adjustments
EXTEND_PATTERN = r"extend\s+(left|right|top|bottom)\s+(?:by\s+)?(\d+)"
SHRINK_PATTERN = r"(?:shrink|reduce)\s+(left|right|top|bottom)\s+(?:by\s+)?(\d+)"
ABSOLUTE_PATTERN = r"\[?\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]?"

# Semantic adjustment patterns
SEMANTIC_PATTERNS = [
    (r"include\s+(?:the\s+)?caption\s+below", "bottom"),
    (r"include\s+(?:the\s+)?caption\s+above", "top"),
    (r"cut(?:s|ting)?\s+off\s+(?:the\s+)?right", "right"),
    (r"cut(?:s|ting)?\s+off\s+(?:the\s+|on\s+the\s+)?left", "left"),
    (r"extend\s+to\s+full\s+width", "width"),
]


def parse_bbox_adjustment(text: str) -> BboxAdjustment | None:
    """Parse a human description of bbox adjustment.

    Supports:
    - Relative: "extend right by 50px"
    - Absolute: "[72, 200, 540, 450]"
    - Semantic: "include the caption below"

    Args:
        text: Human description of the adjustment.

    Returns:
        BboxAdjustment if parseable, None otherwise.
    """
    if not text or not text.strip():
        return None

    text_lower = text.strip().lower()

    # Try parsing absolute coordinates first
    abs_match = re.search(ABSOLUTE_PATTERN, text_lower)
    if abs_match:
        coords = [float(abs_match.group(i)) for i in range(1, 5)]
        return BboxAdjustment(
            adjustment_type=AdjustmentType.ABSOLUTE,
            new_bbox=coords,
        )

    # Try parsing extend
    extend_match = re.search(EXTEND_PATTERN, text_lower)
    if extend_match:
        return BboxAdjustment(
            adjustment_type=AdjustmentType.EXTEND,
            direction=extend_match.group(1),
            amount=int(extend_match.group(2)),
        )

    # Try parsing shrink
    shrink_match = re.search(SHRINK_PATTERN, text_lower)
    if shrink_match:
        return BboxAdjustment(
            adjustment_type=AdjustmentType.SHRINK,
            direction=shrink_match.group(1),
            amount=int(shrink_match.group(2)),
        )

    # Try semantic patterns
    for pattern, direction in SEMANTIC_PATTERNS:
        if re.search(pattern, text_lower):
            return BboxAdjustment(
                adjustment_type=AdjustmentType.SEMANTIC,
                direction=direction,
                amount=30,  # Default semantic adjustment amount
            )

    return None


def apply_adjustment(original: list[float], adjustment: BboxAdjustment) -> list[float]:
    """Apply an adjustment to an existing bbox.

    Args:
        original: Original bbox [x0, y0, x1, y1].
        adjustment: Adjustment to apply.

    Returns:
        New bbox with adjustment applied.
    """
    x0, y0, x1, y1 = original

    if adjustment.adjustment_type == AdjustmentType.ABSOLUTE:
        if adjustment.new_bbox:
            return adjustment.new_bbox
        return original

    amount = adjustment.amount or 0
    direction = adjustment.direction or ""

    if adjustment.adjustment_type == AdjustmentType.EXTEND:
        if direction == "right":
            x1 += amount
        elif direction == "left":
            x0 -= amount
        elif direction == "top":
            y0 -= amount
        elif direction == "bottom":
            y1 += amount
        elif direction == "width":
            # Extend to full page width (assuming 612 pt standard)
            x0 = 36
            x1 = 576

    elif adjustment.adjustment_type == AdjustmentType.SHRINK:
        if direction == "right":
            x1 -= amount
        elif direction == "left":
            x0 += amount
        elif direction == "top":
            y0 += amount
        elif direction == "bottom":
            y1 -= amount

    elif adjustment.adjustment_type == AdjustmentType.SEMANTIC:
        # Apply default semantic adjustments
        if direction == "bottom":
            y1 += amount
        elif direction == "top":
            y0 -= amount
        elif direction == "right":
            x1 += amount
        elif direction == "left":
            x0 -= amount
        elif direction == "width":
            x0 = 36
            x1 = 576

    # Ensure valid bbox (x1 > x0, y1 > y0)
    min_size = 10
    if x1 <= x0:
        x1 = x0 + min_size
    if y1 <= y0:
        y1 = y0 + min_size

    # Ensure non-negative
    x0 = max(0, x0)
    y0 = max(0, y0)

    return [x0, y0, x1, y1]
