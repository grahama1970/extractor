from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import camelot
from camelot import io as camelot_io  # type: ignore


def _bbox_tuple_for(table_obj: Any) -> Optional[tuple]:
    bt = getattr(table_obj, "_bbox", None)
    if not bt and hasattr(table_obj, "cells") and getattr(table_obj, "cells"):
        try:
            xs = [c.x1 for c in table_obj.cells] + [c.x2 for c in table_obj.cells]
            ys = [c.y1 for c in table_obj.cells] + [c.y2 for c in table_obj.cells]
            bt = (min(xs), min(ys), max(xs), max(ys))
        except Exception:
            bt = None
    return bt


def iou_rect(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    inter_w = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    inter_h = max(0.0, min(ay1, by1) - max(ay0, by0))
    inter = inter_w * inter_h
    area_a = max(0.0, (ax1 - ax0)) * max(0.0, (ay1 - ay0))
    area_b = max(0.0, (bx1 - bx0)) * max(0.0, (by1 - by0))
    union = area_a + area_b - inter
    return float(inter / union) if union > 0 else 0.0


def score_table_df(df) -> float:
    try:
        return float(df.astype(str).ne('').sum().sum())
    except Exception:
        return 0.0


def retune_strategies_for_page(
    pdf_path: Path,
    page_index: int,
    ann_rect: List[float],
    *,
    strategies: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Try the Stage 05 Camelot strategies on a single page and pick the best match by IoU + score.

    Returns a dict with the best strategy, its columns/rows, and match metadata.
    """
    page_str = str(int(page_index) + 1)
    ann_box = tuple(float(x) for x in ann_rect) if ann_rect else (0.0, 0.0, 0.0, 0.0)
    best = {
        "strategy": None,
        "iou": 0.0,
        "score": 0.0,
        "columns": [],
        "rows": 0,
    }

    for name, cfg in strategies.items():
        try:
            tables = camelot_io.read_pdf(str(pdf_path), pages=page_str, flavor=cfg.get("flavor", "lattice"), **(cfg.get("params") or {}))
        except Exception:
            continue
        for t in list(tables):
            bt = _bbox_tuple_for(t)
            if not bt:
                continue
            iou = iou_rect(tuple(float(x) for x in bt), ann_box)
            sc = score_table_df(t.df)
            if iou > best["iou"] or (abs(iou - best["iou"]) < 1e-6 and sc > best["score"]):
                best.update({
                    "strategy": name,
                    "iou": iou,
                    "score": sc,
                    "columns": [str(c) for c in list(t.df.columns)],
                    "rows": int(getattr(t.df, "shape", [0, 0])[0]),
                })
    return best

