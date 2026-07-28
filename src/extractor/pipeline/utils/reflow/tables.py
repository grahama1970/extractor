#!/usr/bin/env python3
"""Table processing utilities for Stage 07 Section Reflow.

Handles pandas/Camelot table merge logic, confidence scoring, and block building.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, List, Optional, Tuple

import pandas as pd


# -----------------------------------------------------------------------------
# Cell sanitization
# -----------------------------------------------------------------------------


def normalize_table_text(val: Any) -> str:
    """Normalize table cell text: collapse whitespace, convert None to ''."""
    if val is None:
        return ""
    text = str(val).replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def sanitize_table_cell(val: Any) -> str:
    """Sanitize a table cell value, fixing common OCR/extraction errors."""
    if val is None:
        return ""
    text = str(val).replace("\u00a0", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()

    # Fix common OCR split-word errors
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

    # Fix split in/out tokens
    tokens = text.split()
    if tokens and all(tok.lower() in {"in", "out", "ou", "t"} for tok in tokens):
        merged: list[str] = []
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


def df_map(df: pd.DataFrame, func) -> pd.DataFrame:
    """Elementwise mapping for DataFrames (pandas 2.x compatible)."""
    mapper = getattr(df, "map", None)
    if callable(mapper):
        return mapper(func)
    return df.applymap(func)


# -----------------------------------------------------------------------------
# Table confidence heuristics
# -----------------------------------------------------------------------------


def compute_table_confidence(t: dict[str, Any]) -> float:
    """Compute a table confidence score (0.0–1.0) from pandas/camelot metrics."""
    try:
        pm = t.get("pandas_metrics") or {}
        shape = pm.get("shape") or [0, 0]
        rows = int(shape[0] or 0)
        density = float(pm.get("data_density") or 0.0)
        camel = t.get("camelot_metrics") or {}
        acc = float(camel.get("accuracy") or 0.0)
        white = float(camel.get("whitespace") or 0.0)

        score = 0.0
        score += 0.2 if rows >= 3 else 0.0
        score += min(max(density, 0.0), 1.0) * 0.4
        score += min(max(acc / 100.0, 0.0), 1.0) * 0.4
        score -= min(max(white / 100.0, 0.0), 1.0) * 0.1
        return max(0.0, min(1.0, score))
    except Exception:
        return 0.0


# -----------------------------------------------------------------------------
# Table merge logic
# -----------------------------------------------------------------------------


def compute_table_merges(
    tables: list[dict[str, Any]],
) -> Tuple[
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[Tuple[str, Tuple[int, ...]], dict[str, Any]],
]:
    """Derive merge metadata from Stage 05 tables using a deterministic signature.

    Returns:
        merged_tables_summary: list of merge group summaries
        merged_lookup_by_id: map of table ids -> merge meta
        merged_lookup_by_sig: map of (sig_key, pages tuple) -> merge meta
    """
    merged_tables_summary: list[dict[str, Any]] = []
    merged_lookup_by_id: dict[str, dict[str, Any]] = {}
    merged_lookup_by_sig: dict[Tuple[str, Tuple[int, ...]], dict[str, Any]] = {}

    def _norm_columns(t: dict[str, Any]) -> List[str]:
        """Normalize and return a list of column names from a dictionary."""
        pm = t.get("pandas_metrics") or {}
        cols = pm.get("columns") or t.get("columns") or []
        return [str(c).strip().lower() for c in cols if str(c).strip()]

    def _sig_no_pages(t: dict[str, Any]) -> dict[str, Any]:
        """Return normalized columns and metadata from the input dictionary."""
        cols_norm = _norm_columns(t)
        ncol = len(cols_norm) if cols_norm else t.get("ncol")
        title = (t.get("title") or t.get("header_norm") or "").strip()
        return {"columns": cols_norm, "ncol": ncol, "title": title}

    def _page_idx(t: dict[str, Any]) -> Optional[int]:
        """Return the page index from a dictionary, defaulting to zero."""
        try:
            return int(t.get("page_index", t.get("page", 0)) or 0)
        except Exception:
            return None

    def _logical_key(signature: dict[str, Any]) -> str:
        """Generate a 16-character SHA-256 hash from a signature dictionary."""
        payload = json.dumps(signature, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    sig_groups: dict[str, list[dict[str, Any]]] = {}
    for t in tables:
        sig = _sig_no_pages(t)
        if not (sig["columns"] or sig["ncol"]):
            continue
        base_sig = {"columns": sig["columns"], "ncol": sig["ncol"]}
        sig_key = json.dumps(base_sig, sort_keys=True, ensure_ascii=False)
        sig_groups.setdefault(sig_key, []).append(t)

    def _process_run(items: list[dict[str, Any]], base_sig: dict[str, Any]) -> None:
        """Process a run of items, extracting title and validating pages."""
        if len(items) < 2:
            return
        pages = sorted({p for p in (_page_idx(it) for it in items) if p is not None})
        if len(pages) < 2:
            return
        rep_title = next(
            ((it.get("title") or it.get("header_norm") or "").strip() or None)
            for it in items
            if (it.get("title") or it.get("header_norm"))
        )
        signature = {**base_sig, "title": rep_title or "", "pages": pages}
        logical_key = _logical_key(signature)
        meta = {"merged_table": True, "logical_table_key": logical_key, "merged_pages": pages}
        merged_tables_summary.append(
            {
                "logical_table_key": logical_key,
                "merged_pages": pages,
                "count": len(items),
            }
        )
        merged_lookup_by_sig[
            (json.dumps(base_sig, sort_keys=True, ensure_ascii=False), tuple(pages))
        ] = meta
        for it in items:
            for cand in [
                it.get("id"),
                it.get("table_id"),
                it.get("logical_table_id"),
                it.get("normalized_id"),
            ]:
                if cand:
                    merged_lookup_by_id[str(cand)] = meta
            it.update(meta)

    for sig_key, items in sig_groups.items():
        base_sig = json.loads(sig_key)
        items_sorted = sorted(items, key=lambda x: _page_idx(x) or 0)
        run: list[dict[str, Any]] = []
        for item in items_sorted:
            if not run:
                run = [item]
                continue
            prev_p = _page_idx(run[-1])
            cur_p = _page_idx(item)
            if prev_p is not None and cur_p is not None and cur_p == prev_p + 1:
                run.append(item)
            else:
                _process_run(run, base_sig)
                run = [item]
        _process_run(run, base_sig)

    return merged_tables_summary, merged_lookup_by_id, merged_lookup_by_sig


# -----------------------------------------------------------------------------
# Block builders
# -----------------------------------------------------------------------------


def build_table_block_from_stage05(table: dict[str, Any]) -> dict[str, Any] | None:
    """Return a canonical table block derived from Stage 05 output."""
    pm = table.get("pandas_metrics") or {}
    orig_keys: list[str] = [str(c) for c in (pm.get("columns") or [])]
    inferred = table.get("header_inferred")
    display_cols: list[str] = []
    if isinstance(inferred, list) and inferred and len(inferred) == len(orig_keys):
        display_cols = [sanitize_table_cell(c) for c in inferred]
    else:
        display_cols = [sanitize_table_cell(c) for c in orig_keys]

    rows_raw = table.get("pandas_df") or []
    rows: list[list[Any]] = []
    if display_cols and isinstance(rows_raw, list):
        for row in rows_raw:
            if isinstance(row, dict):
                rows.append(
                    [sanitize_table_cell(row.get(k, "")) for k in orig_keys[: len(display_cols)]]
                )
            elif isinstance(row, list):
                padded = [sanitize_table_cell(v) for v in list(row)[: len(display_cols)]]
                if len(padded) < len(display_cols):
                    padded.extend([None] * (len(display_cols) - len(padded)))
                rows.append(padded)

    rows = [["" if cell is None else cell for cell in r] for r in rows]

    if not display_cols and not rows:
        return None

    confidence: dict[str, Any] = {"status": "high", "density": None, "source": "camelot+pandas"}
    try:
        density_val = float(pm.get("data_density") or 0.0)
        confidence["density"] = density_val
        if density_val < 0.9:
            confidence["status"] = "medium"
    except Exception:
        confidence["density"] = None

    def _norm_hdr(h: str) -> str:
        """Normalize a header string by converting to lowercase and replacing spaces."""
        s = " ".join(str(h or "").strip().lower().split())
        return s.replace(" ", "_")

    header_norm = "|".join([_norm_hdr(h) for h in display_cols]) if display_cols else ""
    logical_table_id = (
        f"lt_{hashlib.sha1(header_norm.encode('utf-8')).hexdigest()[:10]}" if header_norm else None
    )

    return {
        "type": "table",
        "title": None,
        "columns": display_cols,
        "rows": rows,
        "confidence": confidence,
        "markdown": None,
        "markdown_provenance": None,
        "image_refs": [],
        "header_norm": header_norm,
        "logical_table_id": logical_table_id,
        "source": {
            "table_indices": (
                [table.get("table_index")] if table.get("table_index") is not None else []
            ),
            "page_indices": (
                [table.get("page_index")] if table.get("page_index") is not None else []
            ),
        },
    }


__all__ = [
    "normalize_table_text",
    "sanitize_table_cell",
    "df_map",
    "compute_table_confidence",
    "compute_table_merges",
    "build_table_block_from_stage05",
]
