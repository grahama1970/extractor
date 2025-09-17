"""
Simple bbox utility functions for expanding bounding boxes

No complex classes, just simple functions that work!
"""

from typing import List, Tuple


def expand_bbox(
    bbox: List[float],
    expand_ratio: float = 0.3,
    page_width: float = None,
    page_height: float = None,
) -> List[float]:
    """Expand a bounding box by a given ratio.

    Args:
        bbox: [x0, y0, x1, y1] coordinates
        expand_ratio: How much to expand (0.3 = 30%)
        page_width: Optional page width for bounds checking
        page_height: Optional page height for bounds checking

    Returns:
        Expanded bbox [x0, y0, x1, y1]
    """
    x0, y0, x1, y1 = bbox
    width = x1 - x0
    height = y1 - y0

    # Calculate expansion
    expand_x = width * expand_ratio
    expand_y = height * expand_ratio

    # Expand the bbox
    new_x0 = x0 - expand_x
    new_y0 = y0 - expand_y
    new_x1 = x1 + expand_x
    new_y1 = y1 + expand_y

    # Clip to page bounds if provided
    if page_width is not None:
        new_x0 = max(0, new_x0)
        new_x1 = min(page_width, new_x1)

    if page_height is not None:
        new_y0 = max(0, new_y0)
        new_y1 = min(page_height, new_y1)

    return [new_x0, new_y0, new_x1, new_y1]
