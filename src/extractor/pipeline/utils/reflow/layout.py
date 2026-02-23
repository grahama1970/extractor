#!/usr/bin/env python3
"""Layout and geometry utilities for Stage 07 Section Reflow.

Handles IoU calculation, layout ordering, and figure block building.
"""

from __future__ import annotations

from typing import Any


def iou_rect(a: list[float], b: list[float]) -> float:
    """Compute Intersection over Union for two bounding boxes [x0, y0, x1, y1]."""
    if not a or not b or len(a) < 4 or len(b) < 4:
        return 0.0

    try:
        ax0, ay0, ax1, ay1 = float(a[0]), float(a[1]), float(a[2]), float(a[3])
        bx0, by0, bx1, by1 = float(b[0]), float(b[1]), float(b[2]), float(b[3])
    except (TypeError, ValueError):
        return 0.0

    # Intersection
    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)

    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0

    inter_area = (ix1 - ix0) * (iy1 - iy0)

    # Union
    area_a = max(0.0, ax1 - ax0) * max(0.0, ay1 - ay0)
    area_b = max(0.0, bx1 - bx0) * max(0.0, by1 - by0)
    union_area = area_a + area_b - inter_area

    if union_area <= 0:
        return 0.0

    return inter_area / union_area


def horizontal_iou(a: list[float], b: list[float]) -> float:
    """Compute horizontal overlap ratio for two bboxes (for table continuity)."""
    if not a or not b or len(a) < 4 or len(b) < 4:
        return 0.0

    try:
        ax0, ax1 = float(a[0]), float(a[2])
        bx0, bx1 = float(b[0]), float(b[2])
    except (TypeError, ValueError):
        return 0.0

    ix0 = max(ax0, bx0)
    ix1 = min(ax1, bx1)

    if ix1 <= ix0:
        return 0.0

    inter = ix1 - ix0
    union = max(ax1, bx1) - min(ax0, bx0)

    if union <= 0:
        return 0.0

    return inter / union


def build_figure_block_from_stage06(figure: dict[str, Any]) -> dict[str, Any] | None:
    """Return a canonical figure block derived from Stage 06 output."""
    if not isinstance(figure, dict):
        return None

    caption = (figure.get("caption") or figure.get("ai_description") or "").strip() or None
    image_ref = figure.get("image_path") or None

    if not (caption or image_ref):
        return None

    try:
        page_idx = int(figure.get("page", figure.get("page_idx", -1)))
    except Exception:
        page_idx = -1

    block: dict[str, Any] = {
        "type": "figure",
        "title": None,
        "caption": caption,
        "alt": caption or "Figure",
        "image_ref": image_ref,
        "source": {"pages": [page_idx] if page_idx >= 0 else [], "block_ids": []},
    }

    if figure.get("figure_id"):
        block["figure_id"] = figure.get("figure_id")

    return block


def apply_layout_ordering(section: dict[str, Any], iou_threshold: float = 0.5) -> None:
    """Optionally reorder section tables/figures using 06b layout sketch reading_order.

    Matches by IoU between item bbox and elements_original_bbox.
    Safe no-op if sketch missing or fields absent. Modifies section in place.
    """
    sketch = section.get("layout_sketch") or {}
    if not isinstance(sketch, dict):
        return

    reading_order = sketch.get("reading_order") or []
    if not reading_order:
        return

    # Build lookup by element id
    order_lookup: dict[str, int] = {}
    for i, elem in enumerate(reading_order):
        if isinstance(elem, dict) and elem.get("id"):
            order_lookup[str(elem["id"])] = i

    def _order_items(items: list[dict], kind: str) -> None:
        if not items:
            return

        def get_order_key(item: dict) -> int:
            item_id = item.get("id") or item.get(f"{kind}_id")
            if item_id and str(item_id) in order_lookup:
                return order_lookup[str(item_id)]

            # Fall back to IoU matching
            bbox = item.get("bbox") or item.get("bbox0") or []
            for elem in reading_order:
                elem_bbox = elem.get("elements_original_bbox") or elem.get("bbox") or []
                if iou_rect(bbox, elem_bbox) >= iou_threshold:
                    elem_id = elem.get("id")
                    if elem_id and str(elem_id) in order_lookup:
                        return order_lookup[str(elem_id)]
            return 999999

        items.sort(key=get_order_key)

    _order_items(section.get("tables") or [], "table")
    _order_items(section.get("figures") or [], "figure")


__all__ = [
    "iou_rect",
    "horizontal_iou",
    "build_figure_block_from_stage06",
    "apply_layout_ordering",
]
