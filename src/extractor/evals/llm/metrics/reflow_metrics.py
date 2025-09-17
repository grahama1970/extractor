from __future__ import annotations

import json
import unicodedata
from typing import Any, Dict, List, Optional


def _norm_str(s: Any) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = " ".join(s.split())
    return s.strip().lower()


def _get_text_content(block: Dict[str, Any]) -> str:
    t = block.get("text") if isinstance(block.get("text"), str) else block.get("content")
    return t if isinstance(t, str) else ""


def eval_reflow(
    parsed: Dict[str, Any],
    expectations: Dict[str, Any],
    hints: Dict[str, Any],
    *,
    text_min_chars: int = 150,
    row_tolerance: float = 0.10,
    require_top_keys: bool = True,
) -> Dict[str, Any]:
    out = {
        "has_reflowed_json": False,
        "table_count": 0,
        "figure_count": 0,
        "titles_inferred": False,
        "table_columns_ok": None,
        "rows_within_tolerance": None,
        "has_good_text": False,
        "has_required_top_keys": False,
        "missing_titles": None,
        "columns_mismatch": None,
        "rows_out_of_tolerance": None,
        "fail_reason": None,
        "ok": False,
    }
    if not isinstance(parsed, dict):
        return out
    # Required top-level keys
    if isinstance(parsed, dict):
        has_keys = (
            (isinstance(parsed.get("reflowed_json"), (dict, list)))
            and isinstance(parsed.get("ocr_corrections", {}), (dict, list))
            and isinstance(parsed.get("improvements_made", ""), (str, list))
            and isinstance(parsed.get("summary", ""), str)
        )
        out["has_required_top_keys"] = bool(has_keys)
    rj = parsed.get("reflowed_json")
    blocks: List[Dict[str, Any]] = []
    if isinstance(rj, dict):
        blocks = rj.get("blocks") or []
        out["has_reflowed_json"] = True
    elif isinstance(rj, list):
        # Some models return a top-level list of blocks instead of { blocks: [...] }
        blocks = rj
        out["has_reflowed_json"] = True
    else:
        return out
    tables = [b for b in blocks if isinstance(b, dict) and b.get("type") == "table"]
    figures = [b for b in blocks if isinstance(b, dict) and b.get("type") == "figure"]
    out["table_count"] = len(tables)
    out["figure_count"] = len(figures)

    # Expected counts (defaults to 1/1 if provided as such)
    exp_tables = expectations.get("expected_tables")
    exp_figs = expectations.get("expected_figures")
    if exp_tables is not None and out["table_count"] != exp_tables:
        # fail fast if strictly defined
        pass
    if exp_figs is not None and out["figure_count"] != exp_figs:
        pass

    # Titles inferred
    titles_ok = True
    for blk in tables[:1] + figures[:1]:
        title = blk.get("title")
        if not isinstance(title, str) or "inferred" not in title.lower():
            titles_ok = False
    out["titles_inferred"] = bool(titles_ok and bool(tables) and bool(figures))
    out["missing_titles"] = not out["titles_inferred"]

    # Columns and rows checks
    hints_cols = hints.get("columns") or []
    hints_shape = hints.get("shape") or None
    cols_ok = None
    rows_ok = None
    if tables:
        t0 = tables[0]
        content = t0.get("content") or {}
        cols = (
            t0.get("columns")
            or content.get("columns")
            or t0.get("header")
            or content.get("header")
            or []
        )
        rows = t0.get("rows") or content.get("rows") or []
        if hints_cols:
            cols_ok = len(cols) == len(hints_cols)
        if hints_shape and isinstance(hints_shape, list) and len(hints_shape) == 2:
            exp_rows = int(hints_shape[0] or 0)
            tol = max(1, int(round(row_tolerance * max(exp_rows, 1))))
            rows_ok = abs(len(rows) - exp_rows) <= tol
    out["table_columns_ok"] = cols_ok
    out["rows_within_tolerance"] = rows_ok
    out["columns_mismatch"] = cols_ok is False
    out["rows_out_of_tolerance"] = rows_ok is False

    # Good contiguous text ≥ 150 chars
    text_blocks = [b for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
    out["has_good_text"] = any(
        len(_get_text_content(b).strip()) >= int(text_min_chars) for b in text_blocks
    )

    # Final gate
    ok = out["has_reflowed_json"]
    if require_top_keys:
        ok = ok and out["has_required_top_keys"]
    if exp_tables is not None:
        ok = ok and (out["table_count"] == exp_tables)
    if exp_figs is not None:
        ok = ok and (out["figure_count"] == exp_figs)
    ok = ok and out["titles_inferred"] and out["has_good_text"]
    if cols_ok is not None:
        ok = ok and bool(cols_ok)
    if rows_ok is not None:
        ok = ok and bool(rows_ok)
    out["ok"] = bool(ok)
    return out
