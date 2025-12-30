#!/usr/bin/env python3
"""Pandas metrics and scoring utilities for Stage 05 (Table Extractor).

Generates quality metrics and scores for extracted tables.
"""

from __future__ import annotations

from typing import Any, Dict, List

import os
import pandas as pd


def generate_pandas_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """Generate comprehensive metrics from a DataFrame for analysis."""
    if df.empty:
        return {"shape": [0, 0], "error": "Empty DataFrame"}

    total_cells = df.size
    non_empty_cells = df.astype(str).ne("").sum().sum()

    metrics = {
        "shape": list(df.shape),
        "columns": [str(c) for c in df.columns],
        "dtypes": {str(k): str(v) for k, v in df.dtypes.to_dict().items()},
        "null_counts": {str(k): int(v) for k, v in df.isnull().sum().to_dict().items()},
        "total_cells": int(total_cells),
        "non_empty_cells": int(non_empty_cells),
        "data_density": float(non_empty_cells / total_cells) if total_cells > 0 else 0.0,
    }
    return metrics


def score_table(df: pd.DataFrame) -> float:
    """Score a table based on non-empty cell count."""
    if df.empty:
        return 0.0
    return float(df.astype(str).ne("").sum().sum())


def iou(a: List[float], b: List[float]) -> float:
    """Calculate Intersection over Union for two [x0, y0, x1, y1] boxes."""
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


__all__ = [
    "generate_pandas_metrics",
    "score_table",
    "iou",
    "horizontal_iou",
    "sanitize_cell",
    "fragmentation_score",
    "should_retry_fragmentation",
    "has_fragmentation_improvement",
    "should_replace_table",
]


def sanitize_cell(val: Any) -> str:
    """Sanitize cell text to standardize whitespace and fix OCR typos."""
    if val is None:
        return ""
    text = str(val).replace("\u00a0", " ").replace("\n", " ")
    text = " ".join(text.split()).strip()
    replacements = {
        "Subsyste m": "Subsystem",
        "Asynchro nous": "Asynchronous",
        "SUBSY STEM": "SUBSYSTEM",
        "EXECU TE": "EXECUTE",
        "bht_updat e_i": "bht_update_i",
        "bht_predi ction_o": "bht_prediction_o",
        "connexi on": "Connection",
        "Descripti on": "Description",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    tokens = text.split()
    if tokens and all(tok.lower() in {"in", "out", "ou", "t"} for tok in tokens):
        merged: List[str] = []
        i = 0
        while i < len(tokens):
            tok = tokens[i].lower()
            if tok == "in":
                merged.append("in")
            elif tok == "out":
                merged.append("out")
            elif tok == "ou" and i + 1 < len(tokens) and tokens[i + 1].lower() == "t":
                merged.append("out")
                i += 1
            else:
                merged.append(tok)
            i += 1
        text = "/".join(merged)
    return text


def fragmentation_score(df: pd.DataFrame) -> int:
    """Calculate a score indicating how fragmented the table text is (OCR issues)."""
    count = 0
    for cell in df.astype(str).values.flatten():
        if sanitize_cell(cell) != str(cell):
            count += 1
    return count


def should_retry_fragmentation(score: int) -> bool:
    """Check if fragmentation score exceeds retry threshold."""
    return score > max(0, int(os.getenv("TABLE_FRAGMENTATION_RETRY_THRESHOLD", "0")))


def has_fragmentation_improvement(existing: int, new: int) -> bool:
    """Check if new fragmentation score is significantly better than existing."""
    return (existing - new) >= max(1, int(os.getenv("TABLE_FRAGMENTATION_MIN_IMPROVEMENT", "1")))


def should_replace_table(existing_frag: int, new_frag: int, existing_score: float, new_score: float) -> bool:
    """Decide if a new table extraction is better than an existing one."""
    if has_fragmentation_improvement(existing_frag, new_frag):
        return True
    if new_frag == existing_frag and new_score > existing_score:
        return True
    return False
