#!/usr/bin/env python3
"""Table heuristics for Stage 05 (Table Extractor).

Handles stitching, demotion, and header detection logic.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pandas as pd
from loguru import logger

from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.tables.metrics import horizontal_iou

STEP_NAME = "05_table_extractor"

# Configuration constants (env vars)
TABLE_STITCH_MIN_HORIZONTAL_IOU = float(os.getenv("TABLE_STITCH_MIN_HORIZONTAL_IOU", 0.2))
TABLE_STITCH_ALLOW_NEXT_PAGE = os.getenv("TABLE_STITCH_ALLOW_NEXT_PAGE", "true").lower() in (
    "1",
    "true",
    "yes",
    "y",
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
                    new_cols = [str(header_row[k]).strip() or str(i) for i, k in enumerate(keys)]

                    body_df = pd.DataFrame(best.get("pandas_df") or [])
                    if len(body_df.columns) == len(new_cols):
                        body_df.columns = new_cols
                        best["pandas_df"] = body_df.to_dict("records")
                        total_cells = body_df.size
                        non_empty = body_df.astype(str).ne("").sum().sum()
                        best["pandas_metrics"] = {
                            "shape": list(body_df.shape),
                            "columns": [str(c) for c in body_df.columns],
                            "data_density": (
                                float(non_empty / total_cells) if total_cells > 0 else 0.0
                            ),
                        }
                        used_headers.add(id(t))
                except Exception as exc:
                    log_stage_error(STEP_NAME, exc, {"context": "stitch_headers"})
            continue

        stitched.append(t)

    return stitched


def detect_table_caption(pdf_path: Path, page_index: int, bbox: List[float]) -> Optional[str]:
    """Find a nearby caption/title for a table by scanning PDF text above it."""
    import pdf_oxide

    try:
        doc = pdf_oxide.open(str(pdf_path))
        x0, y0, x1, y1 = bbox

        def _scan_band(top: float) -> Optional[str]:
            """Extract text from band above table, look for 'Table N' pattern."""
            band = (x0, max(0, top), x1, y0)
            spans = doc.extract_spans_in_rect(page_index, band)
            # Group by y-position (descending = closest to table first)
            spans = sorted(spans, key=lambda s: -s.get("bbox", [0, 0, 0, 0])[1])
            for s in spans:
                txt = (s.get("text") or "").strip()
                if not txt:
                    continue
                if re.match(r"^\s*Table\s+\d+(?:[-–]\d+)?[.:]", txt, re.IGNORECASE):
                    return txt
            return None

        cap = _scan_band(max(0, y0 - 80))
        if cap:
            return cap

        cap = _scan_band(max(0, y0 - 200))
        if cap:
            return cap

        # Fallback: scan all text above the table on the page
        w, h = doc.page_dimensions(page_index)
        spans = doc.extract_spans_in_rect(page_index, (0, 0, w, y0))
        spans = sorted(spans, key=lambda s: -s.get("bbox", [0, 0, 0, 0])[1])
        for s in spans:
            txt = (s.get("text") or "").strip()
            if not txt:
                continue
            if re.match(r"^\s*Table\s+\d+(?:[-–]\d+)?[.:]", txt, re.IGNORECASE):
                return txt

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


def demote_single_column_tables(result: Dict[str, Any]) -> None:
    """Demote single-column tables to text blocks.

    Single-column "tables" are almost always false positives from:
    - Numbered lists
    - Code blocks
    - Address blocks
    - TOC entries
    - Key-value text patterns

    These are detected by Camelot stream mode but aren't real tables.
    """
    if os.getenv("STAGE05_DEMOTE_SINGLE_COLUMN", "1").lower() not in {"1", "true", "yes", "y"}:
        return

    tables = list(result.get("tables") or [])
    keep: List[Dict[str, Any]] = []
    demoted: List[Dict[str, Any]] = result.get("demoted_text_blocks", []) or []

    for t in tables:
        pm = (t.get("pandas_metrics") or {}).get("shape") or []
        cols = int(pm[1]) if len(pm) > 1 and str(pm[1]).isdigit() else None
        rows = int(pm[0]) if len(pm) > 0 and str(pm[0]).isdigit() else None

        # Keep tables with 2+ columns
        if cols is None or cols >= 2:
            keep.append(t)
            continue

        # Single column - likely false positive
        # Extract text for the demoted block
        txt_parts = []
        src = t.get("pandas_df_raw") or t.get("pandas_df") or []
        if isinstance(src, list):
            for r in src:
                if isinstance(r, dict):
                    txt_parts.extend([str(v).strip() for v in r.values() if v])
                elif isinstance(r, list):
                    txt_parts.extend([str(v).strip() for v in r if v])

        txt = "\n".join(txt_parts)

        try:
            p = int(
                t.get("page_index")
                if t.get("page_index") is not None
                else int(t.get("page_number", 1)) - 1
            )
        except Exception:
            p = 0

        demoted.append(
            {
                "page_idx": p,
                "bbox": t.get("bbox") or [],
                "text": txt,
                "reason": "single_column_false_positive",
                "original_rows": rows,
            }
        )

    result["tables"] = keep
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
                p = int(
                    t.get("page_index")
                    if t.get("page_index") is not None
                    else int(t.get("page_number", 1)) - 1
                )
            except Exception:
                p = 0
            demoted.append(
                {
                    "page_idx": p,
                    "bbox": t.get("bbox") or [],
                    "text": txt,
                    "reason": "sentence_like_single_row",
                }
            )
        else:
            keep.append(t)

    result["tables"] = keep
    if demoted:
        result["demoted_text_blocks"] = demoted


def demote_text_heavy_lattice_tables(result: Dict[str, Any]) -> None:
    """
    Demote tables that appear to be purely text layout artifacts (Lattice False Positives).

    Target:
    - Single column (or effectively single column)
    - High average word count per row > 3
    - Low numeric density
    """
    if os.getenv("STAGE05_DEMOTE_TEXT_TABLES", "1").lower() not in {"1", "true", "yes", "y"}:
        return

    tables = list(result.get("tables") or [])
    keep: List[Dict[str, Any]] = []
    demoted: List[Dict[str, Any]] = result.get("demoted_text_blocks", []) or []

    for t in tables:
        pm = t.get("pandas_metrics") or {}
        shape = pm.get("shape", [0, 0])
        int(shape[0]) if len(shape) > 0 and str(shape[0]).isdigit() else 0
        cols = int(shape[1]) if len(shape) > 1 and str(shape[1]).isdigit() else 0

        # Heuristic 1: Text Blob Detection (Single or Multi-column phantom)
        # Often stream mode splits text into 2-3 columns based on spaces.
        is_text_blob = False

        if cols <= 3:
            # Check content
            src = t.get("pandas_df_raw") or t.get("pandas_df") or []
            total_words = 0
            total_digits = 0
            total_chars = 0
            row_count = 0

            # Flatten to analyze content
            all_text = []
            if isinstance(src, list):
                for r in src:
                    vals = r.values() if isinstance(r, dict) else r
                    # Join cols with space to reconstruct sentence
                    line_parts = [str(v).strip() for v in vals if str(v).strip()]
                    line = " ".join(line_parts)
                    if line:
                        all_text.append(line)
                        words = line.split()
                        total_words += len(words)
                        total_digits += sum(c.isdigit() for c in line)
                        total_chars += len(line)
                        row_count += 1

            avg_words = total_words / max(1, row_count)
            digit_ratio = total_digits / max(1, total_chars)

            # Relaxed Criteria:
            # - Avg words > 5.0 (keeps verbose data tables like Description cols)
            # - Digit ratio < 0.2 (rejects data tables)
            # - Row count > 1 (single rows handled by other heuristic, but fine here too)
            if avg_words > 5.0 and digit_ratio < 0.2:
                is_text_blob = True

        if is_text_blob:
            logger.info(
                f"Demoting text-heavy table idx={t.get('table_index')} page={t.get('page_number')} (cols={cols}, avg_words={avg_words:.1f})"
            )
            try:
                p = int(
                    t.get("page_index")
                    if t.get("page_index") is not None
                    else int(t.get("page_number", 1)) - 1
                )
            except Exception:
                p = 0

            # Join with spaces or newlines?
            # Camelot row-splitting usually implies newlines.
            full_text = "\n".join(all_text)

            demoted.append(
                {
                    "page_idx": p,
                    "bbox": t.get("bbox") or [],
                    "text": full_text,
                    "reason": "text_heavy_lattice_table",
                }
            )
        else:
            keep.append(t)

    result["tables"] = keep
    result["demoted_text_blocks"] = demoted


__all__ = [
    "is_header_row_table",
    "stitch_headers",
    "detect_table_caption",
    "demote_table_headers_to_text",
    "demote_sentence_like_single_row_tables",
    "demote_text_heavy_lattice_tables",
    "coalesce_repeated_header_rows",
]


def _normalize_cell(val: Any) -> str:
    """Normalize cell text for header comparison."""
    s = str(val or "").strip()
    s = s.replace("\u00a0", " ")
    s = " ".join(s.split())
    return s.lower()


def coalesce_repeated_header_rows(df: pd.DataFrame, min_match: float) -> pd.DataFrame:
    """Remove rows that look like repeated headers."""
    if df is None or df.empty:
        return df
    header_proto = None
    try:
        cols = list(df.columns)
        if cols and not all(isinstance(c, int) for c in cols):
            header_proto = [_normalize_cell(c) for c in cols]
    except Exception:
        header_proto = None
    if header_proto is None:
        for _, row in df.iterrows():
            vals = [_normalize_cell(v) for v in row.tolist()]
            if any(vals):
                header_proto = vals
                break
    if not header_proto:
        return df
    keep_mask = []
    for i, row in df.iterrows():
        vals = [_normalize_cell(v) for v in row.tolist()]
        if not any(vals):
            keep_mask.append(True)
            continue
        n = max(1, min(len(vals), len(header_proto)))
        matches = sum(1 for a, b in zip(vals[:n], header_proto[:n]) if a == b and a != "")
        ratio = matches / float(n)
        if ratio >= min_match and i != df.index[0]:
            keep_mask.append(False)
        else:
            keep_mask.append(True)
    try:
        df2 = df.loc[df.index[keep_mask]].copy()
        df2.reset_index(drop=True, inplace=True)
        return df2
    except Exception:
        return df
