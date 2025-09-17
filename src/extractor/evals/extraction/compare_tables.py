from __future__ import annotations

import json
import math
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _norm_str(s: Any) -> str:
    if s is None:
        return ""
    s = str(s)
    s = unicodedata.normalize("NFKC", s)
    s = " ".join(s.split())
    return s.strip().lower()


def iou_rect(a: List[float], b: List[float]) -> float:
    try:
        ax0, ay0, ax1, ay1 = map(float, a)
        bx0, by0, bx1, by1 = map(float, b)
    except Exception:
        return 0.0
    inter_x0 = max(ax0, bx0)
    inter_y0 = max(ay0, by0)
    inter_x1 = min(ax1, bx1)
    inter_y1 = min(ay1, by1)
    inter_w = max(0.0, inter_x1 - inter_x0)
    inter_h = max(0.0, inter_y1 - inter_y0)
    inter = inter_w * inter_h
    area_a = max(0.0, (ax1 - ax0)) * max(0.0, (ay1 - ay0))
    area_b = max(0.0, (bx1 - bx0)) * max(0.0, (by1 - by0))
    union = area_a + area_b - inter
    return float(inter / union) if union > 0 else 0.0


def best_table_match_for_annotation(
    tables: List[Dict[str, Any]], page_index: int, ann_rect: List[float], *, min_iou: float = 0.05
) -> Optional[Dict[str, Any]]:
    candidates = [t for t in tables if int(t.get("page_index", -1)) == int(page_index)]
    best, best_iou = None, 0.0
    for t in candidates:
        bbox = t.get("bbox") or []
        i = iou_rect(ann_rect, bbox)
        if i > best_iou:
            best, best_iou = t, i
    if best and best_iou >= min_iou:
        return best
    return None


def extract_table_columns_rows(table: Dict[str, Any]) -> Tuple[List[str], int]:
    # Prefer pandas_metrics
    pm = table.get("pandas_metrics") or {}
    cols = pm.get("columns") or []
    rows_count = 0
    shape = pm.get("shape") or []
    if isinstance(shape, list) and len(shape) >= 1 and shape[0] is not None:
        try:
            rows_count = int(shape[0])
        except Exception:
            rows_count = 0
    if not rows_count:
        # Try pandas_df
        pdf = table.get("pandas_df") or []
        try:
            rows_count = len(pdf)
        except Exception:
            rows_count = 0
    return [str(c) for c in cols], rows_count


def compare_extracted_to_gold(
    ex_cols: List[str], ex_rows: int, gold: Dict[str, Any], *, row_tol: float = 0.2
) -> Dict[str, Any]:
    gcols = gold.get("columns") or []
    grows = gold.get("rows") or []
    gshape = gold.get("shape")
    # Normalize
    gcols_norm = [_norm_str(c) for c in gcols]
    ex_cols_norm = [_norm_str(c) for c in ex_cols]
    columns_count_ok = len(ex_cols_norm) == len(gcols_norm) if gcols_norm else True
    # Order-insensitive header set equality if names provided
    columns_set_ok = set(ex_cols_norm) == set(gcols_norm) if gcols_norm else True

    expected_rows = (
        len(grows) if grows else (int(gshape[0]) if isinstance(gshape, list) and gshape else None)
    )
    rows_within_tol = True
    if expected_rows is not None and expected_rows >= 1:
        tol = max(1, int(round(row_tol * expected_rows)))
        rows_within_tol = abs(int(ex_rows) - int(expected_rows)) <= tol

    ok = columns_count_ok and columns_set_ok and rows_within_tol
    return {
        "columns_count_ok": columns_count_ok,
        "columns_set_ok": columns_set_ok,
        "rows_within_tolerance": rows_within_tol,
        "ok": ok,
        "extracted": {"columns": ex_cols, "rows_count": ex_rows},
        "gold": {"columns": gcols, "rows_count": expected_rows},
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
