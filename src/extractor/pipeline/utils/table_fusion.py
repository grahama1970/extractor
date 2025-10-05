#!/usr/bin/env python3
"""
table_fusion.py

Multi-strategy table candidate fusion + optional calibrated confidence.

Features:
- Accepts a list of TableCandidate objects (e.g., lattice, stream, future pdfplumber, ML).
- Computes header similarity, numeric stability, fragmentation penalties.
- Optional header/body merge when a header-only candidate + body candidate pair detected.
- Optional learned calibration model (predict_proba) loaded from TABLE_CALIBRATOR_PATH.
- Outputs Stage 05 style table dict with added "confidence" + "fusion" keys.

Environment:
    TABLE_CALIBRATOR_PATH (optional): path to a pickle model exposing predict_proba()
"""

from __future__ import annotations
import os
import pickle
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


@dataclass
class TableCandidate:
    strategy: str
    bbox: Tuple[float, float, float, float]
    df: pd.DataFrame           # cleaned / normalized
    raw_df: pd.DataFrame       # pre-clean (may equal df if not available)
    fragmentation: int
    score: float               # heuristic score (e.g., non-empty cells)
    page_index: int
    table_index: int
    header_row_tokens: List[str] = field(default_factory=list)
    source_meta: Dict[str, Any] = field(default_factory=dict)

    def header_token_set(self) -> set:
        return {t.strip().lower() for t in self.header_row_tokens if isinstance(t, str) and t.strip()}


@dataclass
class FusionResult:
    table: Dict[str, Any]
    diagnostics: Dict[str, Any]


_CALIBRATOR = None
_CAL_FEATURE_ORDER = [
    "fragmentation",
    "header_jaccard_max",
    "numeric_stability",
    "row_count",
    "col_count",
    "strategy_diversity",
]


def _load_calibrator():
    global _CALIBRATOR
    if _CALIBRATOR is not None:
        return
    path = os.getenv("TABLE_CALIBRATOR_PATH")
    if not path:
        return
    try:
        with open(path, "rb") as fh:
            _CALIBRATOR = pickle.load(fh)
    except Exception:
        _CALIBRATOR = None


def _header_jaccard_matrix(cands: List[TableCandidate]) -> List[List[float]]:
    out = []
    for c in cands:
        row = []
        s1 = c.header_token_set()
        for d in cands:
            s2 = d.header_token_set()
            if not s1 and not s2:
                row.append(1.0)
            elif not s1 or not s2:
                row.append(0.0)
            else:
                inter = len(s1 & s2)
                uni = len(s1 | s2) or 1
                row.append(inter / uni)
        out.append(row)
    return out


def _numeric_stability(c: TableCandidate) -> float:
    raw = c.raw_df
    clean = c.df
    total = stable = 0
    try:
        r_rows = min(len(raw), len(clean))
        for i in range(r_rows):
            r_list = raw.iloc[i].tolist()
            c_list = clean.iloc[i].tolist()
            for rv, cv in zip(r_list, c_list):
                rs = str(rv).strip()
                cs = str(cv).strip()
                if rs.replace(".", "", 1).isdigit():
                    total += 1
                    if rs == cs:
                        stable += 1
    except Exception:
        pass
    if total == 0:
        return 1.0
    return stable / total


def _choose_header_body_merge(cands: List[TableCandidate]) -> Optional[Tuple[TableCandidate, TableCandidate]]:
    header_like, body_like = [], []
    for c in cands:
        r, col = c.df.shape
        if r == 1 and col >= 2:
            avg_len = statistics.mean([len(str(x)) for x in c.df.iloc[0].tolist() if str(x).strip()]) or 0
            if avg_len <= 40:
                header_like.append(c)
        elif r >= 2 and col >= 2:
            body_like.append(c)
    best = None
    best_score = -1.0
    for h in header_like:
        for b in body_like:
            if h.df.shape[1] != b.df.shape[1]:
                continue
            hx0, hy0, hx1, hy1 = h.bbox
            bx0, by0, bx1, by1 = b.bbox
            width = max(0.0, min(hx1, bx1) - max(hx0, bx0))
            full = max(hx1, bx1) - min(hx0, bx0) or 1
            horiz_ratio = width / full
            if horiz_ratio < 0.6:
                continue
            score = horiz_ratio - (h.fragmentation * 0.01) - (b.fragmentation * 0.005)
            if score > best_score:
                best_score = score
                best = (h, b)
    return best


def fuse_table_candidates(candidates: List[TableCandidate]) -> FusionResult:
    _load_calibrator()

    if not candidates:
        return FusionResult(table={}, diagnostics={"reason": "no_candidates"})

    # Single candidate path
    if len(candidates) == 1:
        single = candidates[0]
        shape = _to_stage05_shape(
            single,
            merge_type="single",
            structure_prob=None,
            features={"single": True, "fragmentation": single.fragmentation},
            used_strategies=[single.strategy],
            merge_note=None,
        )
        return FusionResult(table=shape, diagnostics={"candidates": 1, "merge_type": "single"})

    # Header similarity
    hj_matrix = _header_jaccard_matrix(candidates)
    header_jaccard_max = max(max(row) for row in hj_matrix) if hj_matrix else 1.0

    # Potential merge pair
    merge_pair = _choose_header_body_merge(candidates)

    # Rank candidates
    enriched = []
    strategies = set()
    for c in candidates:
        ns = _numeric_stability(c)
        rank_score = c.score + (ns * 10) - (c.fragmentation * 0.5)
        enriched.append((c, ns, rank_score))
        strategies.add(c.strategy)
    enriched.sort(key=lambda t: t[2], reverse=True)
    primary = enriched[0][0]
    primary_ns = enriched[0][1]

    merge_type = "single"
    merged_df = primary.df
    merged_raw = primary.raw_df
    used = [primary.strategy]
    merge_note = None

    if merge_pair:
        h, b = merge_pair
        if b.df.shape[0] >= 2:
            try:
                hcols = [str(x).strip() or str(i) for i, x in enumerate(h.df.iloc[0].tolist())]
                if len(hcols) == b.df.shape[1]:
                    body_df = b.df.copy()
                    body_df.columns = hcols
                    merged_df = body_df
                    merged_raw = b.raw_df
                    merge_type = "header_body_merge"
                    used = list({primary.strategy, h.strategy, b.strategy})
                    merge_note = {"header_from": h.strategy, "body_from": b.strategy}
            except Exception:
                pass

    features = {
        "fragmentation": primary.fragmentation,
        "header_jaccard_max": header_jaccard_max,
        "numeric_stability": primary_ns,
        "row_count": merged_df.shape[0],
        "col_count": merged_df.shape[1],
        "strategy_diversity": len(strategies),
    }

    structure_prob = None
    if _CALIBRATOR is not None:
        try:
            vector = [[features[k] for k in _CAL_FEATURE_ORDER]]
            structure_prob = float(_CALIBRATOR.predict_proba(vector)[0][1])
        except Exception:
            structure_prob = None

    fused = TableCandidate(
        strategy=primary.strategy,
        bbox=primary.bbox,
        df=merged_df,
        raw_df=merged_raw,
        fragmentation=primary.fragmentation,
        score=primary.score,
        page_index=primary.page_index,
        table_index=primary.table_index,
        header_row_tokens=list(merged_df.columns),
        source_meta=primary.source_meta,
    )

    final_shape = _to_stage05_shape(
        fused,
        merge_type=merge_type,
        structure_prob=structure_prob,
        features=features,
        used_strategies=used,
        merge_note=merge_note,
    )

    diagnostics = {
        "candidates": len(candidates),
        "selected_strategy": primary.strategy,
        "merge_type": merge_type,
        "structure_prob": structure_prob,
        "used_strategies": used,
        "header_jaccard_max": header_jaccard_max,
    }
    return FusionResult(table=final_shape, diagnostics=diagnostics)


def _to_stage05_shape(
    c: TableCandidate,
    *,
    merge_type: str,
    structure_prob: Optional[float],
    features: Dict[str, Any],
    used_strategies: Optional[List[str]],
    merge_note: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    df = c.df
    rows_dict = df.to_dict("records")

    confidence = {
        "structure_prob": structure_prob,
        "fragmentation": c.fragmentation,
        "header_jaccard": features.get("header_jaccard_max"),
        "numeric_stability": features.get("numeric_stability"),
        "merge_type": merge_type,
        "source_strategies": used_strategies or [c.strategy],
    }
    if merge_note:
        confidence["merge_note"] = merge_note

    return {
        "page_number": c.page_index + 1,
        "page_index": c.page_index,
        "table_index": c.table_index,  # caller may overwrite
        "bbox": list(c.bbox),
        "extraction_method": c.source_meta.get("extraction_method", "fused"),
        "strategy": c.strategy,
        "fragmentation_score": c.fragmentation,
        "pandas_df": rows_dict,            # keep legacy dict rows
        "pandas_metrics": {
            "shape": list(df.shape),
            "columns": [str(x) for x in df.columns],
        },
        "row_count": df.shape[0],
        "col_count": df.shape[1],
        "confidence": confidence,
        "fusion": {
            "rank_features": features,
        },
    }

