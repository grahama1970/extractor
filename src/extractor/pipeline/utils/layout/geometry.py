#!/usr/bin/env python3
"""Geometry utilities for Stage 06b (Layout Sketcher).

Pure math functions for grid mapping and layout analysis.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any, Dict, List


def norm(v: float, a: float, b: float) -> float:
    """Normalize v to [0,1] within [a,b]."""
    span = b - a
    if span <= 0:
        return 0.0
    return max(0.0, min(1.0, (v - a) / span))


def grid_bbox(bbox: List[float], page: List[float], grid: int) -> Dict[str, int]:
    """Map page bbox → grid cells using half-open contract [x0,x1), [y0,y1).

    - floor for starts, ceil for ends
    - clamp to [0, grid]
    - ensure non-degenerate (at least 1x1 cell)
    """
    x0, y0, x1, y1 = bbox
    px0, py0, px1, py1 = page

    nx0 = norm(x0, px0, px1)
    ny0 = norm(y0, py0, py1)
    nx1 = norm(x1, px0, px1)
    ny1 = norm(y1, py0, py1)

    gx0 = max(0, min(grid, int(math.floor(nx0 * grid))))
    gy0 = max(0, min(grid, int(math.floor(ny0 * grid))))
    gx1 = max(0, min(grid, int(math.ceil(nx1 * grid))))
    gy1 = max(0, min(grid, int(math.ceil(ny1 * grid))))

    # Ensure non-degenerate
    if gx1 <= gx0:
        gx1 = min(grid, gx0 + 1)
    if gy1 <= gy0:
        gy1 = min(grid, gy0 + 1)

    return {"x0": gx0, "y0": gy0, "x1": gx1, "y1": gy1}


def area(b: List[float]) -> float:
    """Calculate area of a bbox."""
    try:
        return max(0.0, float(b[2] - b[0])) * max(0.0, float(b[3] - b[1]))
    except Exception:
        return 0.0


def aspect(b: List[float]) -> float:
    """Calculate aspect ratio (width/height) of a bbox."""
    try:
        h = max(1e-6, float(b[3] - b[1]))
        return float(b[2] - b[0]) / h
    except Exception:
        return 1.0


def iou(a: List[float], b: List[float]) -> float:
    """Calculate Intersection over Union for two bboxes."""
    try:
        ax0, ay0, ax1, ay1 = a
        bx0, by0, bx1, by1 = b
        inter_w = max(0.0, min(ax1, bx1) - max(ax0, bx0))
        inter_h = max(0.0, min(ay1, by1) - max(ay0, by0))
        inter = inter_w * inter_h
        area_a = max(0.0, (ax1 - ax0)) * max(0.0, (ay1 - ay0))
        area_b = max(0.0, (bx1 - bx0)) * max(0.0, (by1 - by0))
        union = area_a + area_b - inter
        return float(inter / union) if union > 0 else 0.0
    except Exception:
        return 0.0


def horizontal_iou(a: List[float], b: List[float]) -> float:
    """Calculate 1D Intersection over Union on the X-axis only."""
    try:
        ax0, _, ax1, _ = a
        bx0, _, bx1, _ = b
        inter = max(0.0, min(ax1, bx1) - max(ax0, bx0))
        uni = max(ax1, bx1) - min(ax0, bx0)
        return float(inter / uni) if uni > 0 else 0.0
    except Exception:
        return 0.0


def summ(text: str, limit: int = 80) -> str:
    """Summarize text to a limit."""
    if not text:
        return ""
    s = " ".join(str(text).split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


def norm_text(s: str) -> str:
    """Normalize text (collapsed whitespace, preserves case)."""
    return " ".join((s or "").split())


def text_sha1(s: str) -> str:
    """Compute SHA1 hash of normalized text."""
    normed = norm_text(s)
    return hashlib.sha1(normed.encode("utf-8")).hexdigest()


def union_bbox(elements: List[Dict[str, Any]]) -> List[float]:
    """Calculate union bbox of all elements."""
    x0, y0 = float("inf"), float("inf")
    x1, y1 = float("-inf"), float("-inf")
    found = False
    for e in elements:
        b = e.get("bbox")
        if not (isinstance(b, (list, tuple)) and len(b) == 4):
            continue
        ex0, ey0, ex1, ey1 = map(float, b)
        x0, y0, x1, y1 = min(x0, ex0), min(y0, ey0), max(x1, ex1), max(y1, ey1)
        found = True
    return [x0, y0, x1, y1] if found else [0.0, 0.0, 0.0, 0.0]


__all__ = [
    "norm",
    "grid_bbox",
    "area",
    "aspect",
    "iou",
    "horizontal_iou",
    "summ",
    "norm_text",
    "text_sha1",
    "union_bbox",
]
