#!/usr/bin/env python3
"""Geometry utilities for Stage 09a (PDF Annotator).

Bbox conversion and coordinate transformations for PyMuPDF.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import fitz

from extractor.pipeline.utils.reliability import log_stage_error

STEP_NAME = "09a_pdf_annotator"


def safe_get_bbox(obj: Dict[str, Any]) -> Optional[List[float]]:
    """Safely extract bbox from an object."""
    bb = obj.get("bbox") or obj.get("box")
    if not isinstance(bb, (list, tuple)) or len(bb) != 4:
        return None
    try:
        return [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])]
    except Exception:
        return None


def rect_from_pdf_bbox(page: fitz.Page, bbox: List[float]) -> fitz.Rect:
    """Convert bbox to PyMuPDF rect (assumes top-left origin)."""
    x0, y0, x1, y1 = bbox
    x_lo, x_hi = sorted((x0, x1))
    y_lo, y_hi = sorted((y0, y1))
    rect = fitz.Rect(x_lo, y_lo, x_hi, y_hi) & page.rect
    if rect.y1 < rect.y0:
        rect = fitz.Rect(rect.x0, rect.y1, rect.x1, rect.y0)
    if rect.width <= 0 or rect.height <= 0:
        rect = fitz.Rect(
            rect.x0, rect.y0,
            rect.x0 + max(1.0, rect.width),
            rect.y0 + max(1.0, rect.height)
        ) & page.rect
    return rect


def rect_for_kind(page: fitz.Page, bbox: List[float], kind: str) -> fitz.Rect:
    """Convert bbox to page rect with per-kind origin rules.
    
    - Camelot/requirements (table, table_merged, table_rejected, requirement)
      are PDF-origin bottom-left.
    - Others (section, figure, header_candidate, text_chunk, etc.) are top-left.
    """
    if kind in {"table", "table_merged", "table_rejected", "requirement"}:
        # Flip Y for bottom-left origin bboxes
        x0, y0, x1, y1 = bbox
        h = float(page.rect.height)
        flipped = [x0, h - y1, x1, h - y0]
        return rect_from_pdf_bbox(page, flipped)
    return rect_from_pdf_bbox(page, bbox)


def coerce_page(*args: Any) -> Optional[int]:
    """Coerce various page representations to 0-based index."""
    for val in args:
        if val is None:
            continue
        if isinstance(val, int):
            return val
        if isinstance(val, float):
            return int(val)
        if isinstance(val, str):
            try:
                return int(val)
            except ValueError:
                continue
    return None


__all__ = [
    "safe_get_bbox",
    "rect_from_pdf_bbox",
    "rect_for_kind",
    "coerce_page",
]
