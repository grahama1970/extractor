#!/usr/bin/env python3
"""Table heuristics for Stage 05 (Table Extractor).

Handles stitching, demotion, and header detection logic.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
from loguru import logger

from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.tables.metrics import horizontal_iou

STEP_NAME = "05_table_extractor"

# Configuration constants (env vars)
TABLE_STITCH_MIN_HORIZONTAL_IOU = float(os.getenv("TABLE_STITCH_MIN_HORIZONTAL_IOU", 0.2))
TABLE_STITCH_ALLOW_NEXT_PAGE = os.getenv("TABLE_STITCH_ALLOW_NEXT_PAGE", "true").lower() in (
    "1", "true", "yes", "y",
)
STAGE05_DEMOTE_MAX_ROWS = int(os.getenv("STAGE05_DEMOTE_MAX_ROWS", "4"))


def is_header_row_table(t: Dict[str, Any]) -> bool:
    """Keyword-agnostic heuristic for header-only tables.
    
    Criteria:
    - Exactly 1 row and at least 2 columns.
    - Average cell length <= 32 chars.
    - Combined digit ratio < 0.5.
    """
    metrics = t.get("pandas_metrics", {}) or {}
    shape = metrics.get("shape", [0, 0])
    rows = int(shape[0]) if isinstance(shape, (list, tuple)) and shape else 0
    cols = int(shape[1]) if isinstance(shape, (list, tuple)) and shape else 0
    
    if rows != 1 or cols < 2:
        return False
        
    try:
        first = (t.get("pandas_df") or [{}])[0]
        keys = sorted(first.keys(), key=lambda k: int(str(k)) if str(k).isdigit() else 9999)
        values = [str(first[k]).strip() for k in keys]
        
        if not values:
            return False
            
        avg_len = sum(len(v) for v in values) / max(1, len(values))
        digits = sum(sum(ch.isdigit() for ch in v) for v in values)
        total = sum(len(v) for v in values) or 1
        digit_ratio = digits / total
        
        return (avg_len <= 32) and (digit_ratio < 0.5)
    except Exception:
        return False


def stitch_headers(tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge header-only tables into the body table below them.
    
    Checks horizontal overlap and page adjacency.
    """
    if not tables:
        return tables
        
    # Index candidates by page
    by_page: Dict[int, List[Dict[str, Any]]] = {}
    for t in tables:
        by_page.setdefault(int(t.get("page_index", 0)), []).append(t)

    used_headers: Set[int] = set()
    stitched: List[Dict[str, Any]] = []
    
    for t in tables:
        if is_header_row_table(t):
            page = int(t.get("page_index", 0))
            bbox = t.get("bbox", [])
            cols = int((t.get("pandas_metrics", {}) or {}).get("shape", [0, 0])[1] or 0)
            
            candidate_pages = [page]
            if TABLE_STITCH_ALLOW_NEXT_PAGE:
                candidate_pages.append(page + 1)
                
            candidates = []
            for p in candidate_pages:
                candidates.extend(by_page.get(p, []) or [])
            
            best = None
            best_score = -1.0
            
            for c in candidates:
                if c is t:
                    continue
                    
                m = c.get("pandas_metrics", {}) or {}
                shape = m.get("shape", [0, 0])
                rows_c = int(shape[0]) if isinstance(shape, (list, tuple)) and shape else 0
                cols_c = int(shape[1]) if isinstance(shape, (list, tuple)) and shape else 0
                
                if rows_c < 2 or cols_c != cols:
                    continue
                    
                align_iou = horizontal_iou(bbox, c.get("bbox", []))
                if align_iou < TABLE_STITCH_MIN_HORIZONTAL_IOU:
                    continue
                    
                score = float(c.get("score", 0.0)) + align_iou
                if score > best_score:
                    best_score = score
                    best = c
            
            if best is not None:
                try:
                    header_row = (t.get("pandas_df") or [{}])[0]
                    keys = sorted(
                        header_row.keys(),
                        key=lambda k: int(str(k)) if str(k).isdigit() else 9999,
                    )
                    new_cols = [
                        str(header_row[k]).strip() or str(i) for i, k in enumerate(keys)
                    ]
                    
                    body_df = pd.DataFrame(best.get("pandas_df") or [])
                    if len(body_df.columns) == len(new_cols):
                        body_df.columns = new_cols
                        best["pandas_df"] = body_df.to_dict("records")
                        total_cells = body_df.size
                        non_empty = body_df.astype(str).ne("").sum().sum()
                        best["pandas_metrics"] = {
                            "shape": list(body_df.shape),
                            "columns": [str(c) for c in body_df.columns],
                            "data_density": float(non_empty / total_cells) if total_cells > 0 else 0.0,
                        }
                        used_headers.add(id(t))
                except Exception as exc:
                    log_stage_error(STEP_NAME, exc, {"context": "stitch_headers"})
            continue
            
        stitched.append(t)
        
    return stitched


def detect_table_caption(pdf_path: Path, page_index: int, bbox: List[float]) -> Optional[str]:
    """Find a nearby caption/title for a table by scanning PDF text above it."""
    import fitz
    
    try:
        doc = fitz.open(str(pdf_path))
        page = doc[page_index]
        rect = fitz.Rect(*bbox)
        
        def _scan_band(top: float) -> Optional[str]:
            band = fitz.Rect(rect.x0, max(0, top), rect.x1, rect.y0)
            blocks = page.get_text("blocks", clip=band)
            blocks = sorted(blocks, key=lambda b: -b[1])
            for b in blocks:
                txt = (b[4] or "").strip()
                if not txt:
                    continue
                if re.match(r"^\s*Table\s+\d+(?:[-–]\d+)?[.:]", txt, re.IGNORECASE):
                    return txt
            return None

        cap = _scan_band(max(0, rect.y0 - 80))
        if cap:
            doc.close()
            return cap
            
        cap = _scan_band(max(0, rect.y0 - 200))
        if cap:
            doc.close()
            return cap
            
        blocks = page.get_text("blocks")
        above = [b for b in blocks if b[3] <= rect.y0]
        above = sorted(above, key=lambda b: -b[1])
        
        for b in above:
            txt = (b[4] or "").strip()
            if not txt:
                continue
            if re.match(r"^\s*Table\s+\d+(?:[-–]\d+)?[.:]", txt, re.IGNORECASE):
                doc.close()
                return txt
                
        doc.close()
        return None
    except Exception as exc:
        log_stage_error(STEP_NAME, exc, {"context": "detect_caption"})
        return None


def demote_table_headers_to_text(result: Dict[str, Any]) -> None:
    """Detect one-line numbered headings captured as small tables.
    
    Adds result["demoted_text_blocks"] with {page_idx, bbox, text}.
    """
    if os.getenv("STAGE05_DEMOTE_TABLE_HEADERS", "1").lower() not in {"1", "true", "yes", "y"}:
        return
        
    pat = re.compile(r"^(?:\d+\.){1,6}\s+\S.*")
    demoted: List[Dict[str, Any]] = []
    
    for t in result.get("tables") or []:
        try:
            pm = t.get("pandas_metrics") or {}
            shape = pm.get("shape") or [0, 0]
            rows = int(shape[0] or 0)
            cols = int(shape[1] or 0)
        except Exception:
            rows, cols = 0, 0
            
        if cols > 2 or rows > STAGE05_DEMOTE_MAX_ROWS:
            continue
            
        cells: List[str] = []
        src = t.get("pandas_df_raw") or t.get("pandas_df") or []
        if isinstance(src, list):
            for r in src[:8]:
                if isinstance(r, dict):
                    cells.extend([str(v).strip() for v in r.values()])
                elif isinstance(r, list):
                    cells.extend([str(v).strip() for v in r])
                    
        head = next((c for c in cells if c), None)
        if not head or not pat.match(head):
            continue
        if head.endswith(".") or head.endswith(";"):
            continue
            
        try:
            if t.get("page_index") is not None:
                p = int(t.get("page_index"))
            else:
                p = int(t.get("page_number", 1)) - 1
        except Exception:
            p = 0
            
        demoted.append({"page_idx": p, "bbox": t.get("bbox") or [], "text": head})
        
    if demoted:
        result["demoted_text_blocks"] = demoted


def demote_sentence_like_single_row_tables(result: Dict[str, Any]) -> None:
    """Demote single-row sentence-like tables to text blocks."""
    if os.getenv("STAGE05_DEMOTE_SENTENCE_ROW", "1").lower() not in {"1", "true", "yes", "y"}:
        return
        
    tables = list(result.get("tables") or [])
    keep: List[Dict[str, Any]] = []
    demoted: List[Dict[str, Any]] = result.get("demoted_text_blocks", []) or []
    
    for t in tables:
        pm = (t.get("pandas_metrics") or {}).get("shape") or []
        rows = int(pm[0]) if len(pm) > 0 and str(pm[0]).isdigit() else None
        
        if rows != 1:
            keep.append(t)
            continue
            
        # Get text from table
        txt = ""
        src = t.get("pandas_df_raw") or t.get("pandas_df") or []
        if isinstance(src, list):
            for r in src[:1]:
                if isinstance(r, dict):
                    txt = " ".join([str(v).strip() for v in r.values()])
                elif isinstance(r, list):
                    txt = " ".join([str(v).strip() for v in r])
                    
        words = len(txt.split())
        looks_sentence = words >= 6 and bool(re.search(r"[\.!?]\s*$", txt))
        
        if looks_sentence:
            try:
                p = int(t.get("page_index") if t.get("page_index") is not None else int(t.get("page_number", 1)) - 1)
            except Exception:
                p = 0
            demoted.append({
                "page_idx": p,
                "bbox": t.get("bbox") or [],
                "text": txt,
                "reason": "sentence_like_single_row"
            })
        else:
            keep.append(t)
            
    result["tables"] = keep
    if demoted:
        result["demoted_text_blocks"] = demoted


__all__ = [
    "is_header_row_table",
    "stitch_headers",
    "detect_table_caption",
    "demote_table_headers_to_text",
    "demote_sentence_like_single_row_tables",
]
