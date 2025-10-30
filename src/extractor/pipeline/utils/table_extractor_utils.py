#!/usr/bin/env python3
"""Pure helpers for Stage 05 (Table Extractor)."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List
import pandas as pd


def _stable_table_hash(table: Dict[str, Any]) -> str:
    import hashlib
    h = hashlib.sha256()
    payload = {
        "bbox": table.get("bbox"),
        "cols": table.get("columns") or table.get("header") or [],
        "shape": (table.get("pandas_metrics") or {}).get("shape") or [],
    }
    h.update(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return h.hexdigest()


def _should_assist(table: Dict[str, Any]) -> bool:
    pm = table.get("pandas_metrics") or {}
    density = float(pm.get("data_density") or 0.0)
    frag = int(table.get("fragmentation_score") or 0)
    camel = table.get("camelot_metrics") or {}
    acc = float(camel.get("accuracy") or 0.0) / 100.0
    if frag >= int(os.getenv("TABLE_LLM_ASSIST_FRAG_MIN", "4")):
        return True
    if density <= float(os.getenv("TABLE_LLM_ASSIST_DENSITY_MAX", "0.25")):
        return True
    if acc and acc <= float(os.getenv("TABLE_LLM_ASSIST_ACCURACY_MAX", "0.55")):
        return True
    return False


def _headers_from_table(t: Dict[str, Any]) -> List[str]:
    if t.get("header"):
        return [str(x) for x in t["header"]]
    if t.get("columns"):
        return [str(x) for x in t["columns"]]
    rows = t.get("rows") or []
    return [str(x) for x in (rows[0] if rows else [])]


def _apply_headers(t: Dict[str, Any], headers: List[str]) -> None:
    n = len(headers)
    if t.get("header") and isinstance(t["header"], list) and len(t["header"]) == n:
        t["header"] = headers
    elif t.get("columns") and isinstance(t["columns"], list) and len(t["columns"]) == n:
        t["columns"] = headers


def _extract_table_text_for_heuristics(t: Dict[str, Any]) -> str:
    src = t.get("pandas_df_raw") or t.get("pandas_df")
    cells = []
    if isinstance(src, list):
        for r in src:
            if isinstance(r, dict):
                cells.extend([str(v).strip() for v in r.values()])
            elif isinstance(r, list):
                cells.extend([str(v).strip() for v in r])
    elif isinstance(src, dict):
        for r in src.values():
            if isinstance(r, list):
                cells.extend([str(v).strip() for v in r])
    return " ".join(cells[:50])


def sanitize_cell(val: Any) -> str:
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
    count = 0
    for cell in df.astype(str).values.flatten():
        if sanitize_cell(cell) != str(cell):
            count += 1
    return count


def should_retry_fragmentation(score: int) -> bool:
    return score > max(0, int(os.getenv("TABLE_FRAGMENTATION_RETRY_THRESHOLD", "0")))


def has_fragmentation_improvement(existing: int, new: int) -> bool:
    return (existing - new) >= max(1, int(os.getenv("TABLE_FRAGMENTATION_MIN_IMPROVEMENT", "1")))


def should_replace_table(existing_frag: int, new_frag: int, existing_score: float, new_score: float) -> bool:
    if has_fragmentation_improvement(existing_frag, new_frag):
        return True
    if new_frag == existing_frag and new_score > existing_score:
        return True
    return False


def _normalize_cell(val: Any) -> str:
    s = str(val or "").strip()
    s = s.replace("\u00a0", " ")
    s = " ".join(s.split())
    return s.lower()


def coalesce_repeated_header_rows(df: pd.DataFrame, min_match: float) -> pd.DataFrame:
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
