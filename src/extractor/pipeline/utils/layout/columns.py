#!/usr/bin/env python3
"""Column detection utilities for Stage 06b (Layout Sketcher).

Detects multi-column layouts and assigns elements to columns.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def detect_columns(
    elements: List[Dict[str, Any]],
    page_bbox: List[float],
    min_gap_ratio: float = 0.04,
) -> List[List[float]]:
    """Detect 1–3 columns deterministically using x-center gaps.
    
    Returns list of [x0, x1] column bounds in page coordinates.
    """
    if not elements:
        return [[page_bbox[0], page_bbox[2]]]
    
    centers = []
    for e in elements:
        box = e.get("bbox")
        if isinstance(box, (list, tuple)) and len(box) == 4:
            centers.append((box[0] + box[2]) / 2.0)
    
    if not centers:
        return [[page_bbox[0], page_bbox[2]]]
    
    centers = sorted(centers)
    page_width = max(1.0, page_bbox[2] - page_bbox[0])
    min_gap = page_width * min_gap_ratio
    
    # Find significant gaps
    gaps = []
    for i in range(1, len(centers)):
        gap = centers[i] - centers[i - 1]
        if gap >= min_gap:
            mid = (centers[i] + centers[i - 1]) / 2.0
            gaps.append((gap, mid))
    
    # Sort by gap size, take up to 2 largest gaps
    gaps.sort(key=lambda x: -x[0])
    dividers = sorted([g[1] for g in gaps[:2]])
    
    # Build column ranges
    cols = []
    prev = page_bbox[0]
    for d in dividers:
        if d > prev + 10:  # Minimum column width
            cols.append([prev, d])
            prev = d
    cols.append([prev, page_bbox[2]])
    
    return cols


def assign_cols_and_span(
    bbox: List[float],
    columns: List[List[float]],
) -> Tuple[List[int], bool]:
    """Return ([col_ids], spans_columns) based on overlap with column bands."""
    if not columns:
        return [0], False
    
    x0, _, x1, _ = bbox
    matched = []
    
    for i, (cx0, cx1) in enumerate(columns):
        # Calculate overlap
        inter = max(0.0, min(x1, cx1) - max(x0, cx0))
        if inter > 0:
            matched.append(i)
    
    if not matched:
        # Find closest column
        xc = (x0 + x1) / 2.0
        closest = 0
        min_dist = float("inf")
        for i, (cx0, cx1) in enumerate(columns):
            col_center = (cx0 + cx1) / 2.0
            dist = abs(xc - col_center)
            if dist < min_dist:
                min_dist = dist
                closest = i
        matched = [closest]
    
    spans = len(matched) > 1
    return matched, spans


def col_id_for(xc: float, columns: List[List[float]]) -> int:
    """Get column ID for a given x-center coordinate."""
    for i, (cx0, cx1) in enumerate(columns):
        if cx0 <= xc <= cx1:
            return i
    return 0


__all__ = [
    "detect_columns",
    "assign_cols_and_span",
    "col_id_for",
]
