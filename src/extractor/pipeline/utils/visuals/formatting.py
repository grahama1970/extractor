#!/usr/bin/env python3
"""Text formatting utilities for Stage 09a (PDF Annotator).

Label generation and text wrapping for annotations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    import fitz  # PyMuPDF (optional — regression testing only)
except ImportError:
    fitz = None  # type: ignore[assignment]


STEP_NAME = "09a_pdf_annotator"


def wrap_label_lines(
    page: fitz.Page,
    text: str,
    font: float,
    max_width: float,
    max_lines: int = 3,
) -> List[str]:
    """Wrap text to fit within max_width, returning list of lines."""
    text = (text or "").strip()
    if not text:
        return []
    if max_width <= font * 3:
        truncated = text
        while fitz.get_text_length(truncated, fontsize=font) > max_width and len(truncated) > 1:
            truncated = truncated[:-1]
        if len(truncated) < len(text):
            truncated = truncated.rstrip(" .,;") + "…"
        return [truncated]

    words = text.split()
    if not words:
        return []

    lines: List[str] = []
    idx = 0
    while idx < len(words) and len(lines) < max_lines:
        current = words[idx]
        idx += 1
        while idx < len(words):
            candidate = f"{current} {words[idx]}"
            if fitz.get_text_length(candidate, fontsize=font) <= max_width:
                current = candidate
                idx += 1
            else:
                break
        lines.append(current)
    if idx < len(words) and lines:
        lines[-1] = lines[-1].rstrip(" .,;") + "…"
    return lines


def format_label(kind: str, payload: Dict[str, Any], override: Optional[str] = None) -> str:
    """Generate a human-readable label for an overlay."""
    if override:
        base = str(override)
    elif kind.startswith("table") and kind != "table_rejected":
        idx = payload.get("table_index") or payload.get("tableNumber")
        name = payload.get("title") or payload.get("caption") or payload.get("logical_table_key")
        pages = payload.get("pages_in_group") or payload.get("page_indices")
        page_str = ""
        if isinstance(pages, list) and pages:
            try:
                page_str = f" (pages {', '.join(str(int(p)) for p in pages)})"
            except Exception:
                page_str = f" (pages {', '.join(str(p) for p in pages)})"
        if idx and name:
            base = f"Table {idx}: {name}{page_str}"
        elif idx:
            base = f"Table {idx}{page_str}"
        elif name:
            base = f"Table: {name}{page_str}"
        else:
            base = "Table"
    elif kind == "table_rejected":
        reason = payload.get("reason") or ""
        base = f"Rejected table{': ' + reason if reason else ''}"
    elif kind == "table_merged":
        key = payload.get("logical_table_key") or payload.get("group")
        pages = payload.get("pages_in_group")
        page_str = ""
        if isinstance(pages, list) and pages:
            try:
                page_str = f" (pages {', '.join(str(int(p)) for p in pages)})"
            except Exception:
                page_str = f" (pages {', '.join(str(p) for p in pages)})"
        base = f"Merged table {key}{page_str}" if key else f"Merged table{page_str}"
    elif kind == "section":
        title = payload.get("title") or payload.get("heading") or payload.get("id")
        if title and payload.get("continuation"):
            title = f"{title} (cont.)"
        base = f"Section: {title}" if title else "Section"
    elif kind == "figure":
        fid = payload.get("figure_id")
        title = payload.get("title") or payload.get("caption")
        if fid and title:
            base = f"Figure {fid}: {title}"
        elif fid:
            base = f"Figure {fid}"
        elif title:
            base = f"Figure: {title}"
        else:
            base = "Figure"
    elif kind == "header_candidate":
        verdict = payload.get("verdict")
        base = f"Header candidate: {verdict}" if verdict else "Header candidate"
    elif kind.startswith("requirement"):
        rid = payload.get("requirement_id") or payload.get("id")
        title = payload.get("title")
        if rid and title:
            base = f"Requirement {rid}: {title}"
        elif rid:
            base = f"Requirement {rid}"
        elif title:
            base = f"Requirement: {title}"
        else:
            base = "Requirement"
        if payload.get("conditional"):
            base += " (conditional)"
    else:
        base = override or kind.replace("_", " ").title()
    base = " ".join(str(base).split())
    return base[:140]


def stable_overlay_id(
    kind: str,
    page_index: int,
    payload: Dict[str, Any],
    fallback: int,
) -> str:
    """Generate a stable identifier for an overlay."""
    page_token = f"@{page_index + 1}" if page_index >= 0 else ""

    def _first_str(keys: List[str]) -> Optional[str]:
        """Return the first non-empty string value from a list of keys."""
        for key in keys:
            val = payload.get(key)
            if val is None:
                continue
            if isinstance(val, (list, tuple)):
                if not val:
                    continue
                return str(val[0])
            return str(val)
        return None

    if kind == "section":
        sid = _first_str(["id", "section_id", "sectionId"])
        if sid:
            return f"SEC::{sid}{page_token}"
    if kind in {"table", "table_merged", "table_rejected"}:
        key = _first_str(["logical_table_key", "group", "table_index", "tableNumber"])
        if key:
            return f"TBL::{key}{page_token}"
    if kind == "figure":
        fid = _first_str(["figure_id", "id"])
        if fid:
            return f"FIG::{fid}{page_token}"
    if kind.startswith("requirement"):
        rid = _first_str(["requirement_id", "id"])
        if rid:
            return f"REQ::{rid}{page_token}"
    if kind.startswith("reflow_"):
        block_id = _first_str(["block_id", "source_block_id", "hash"])
        if block_id:
            return f"RFL::{block_id}{page_token}"
    if kind == "header_candidate":
        bid = _first_str(["block_id", "id"])
        if bid:
            return f"HDR::{bid}{page_token}"
    return f"{kind.upper()}::ov{fallback}{page_token}"


def headers_preview_from_table(table_obj: Dict[str, Any], limit: int = 6) -> Optional[str]:
    """Extract headers preview string from table object."""
    headers = table_obj.get("headers")
    if not headers:
        df = table_obj.get("pandas_df_raw") or table_obj.get("pandas_df")
        if isinstance(df, list) and df:
            first_row = df[0]
            if isinstance(first_row, dict):
                headers = list(first_row.keys())
            elif isinstance(first_row, list):
                headers = first_row
    if isinstance(headers, list) and headers:
        return " | ".join(str(h).strip() for h in headers[:limit])
    return None


def rows_preview_from_table(
    table_obj: Dict[str, Any],
    max_rows: int = 4,
    max_cols: int = 4,
    max_chars: int = 70,
) -> List[str]:
    """Extract row previews from table object."""
    rows: List[str] = []
    headers = table_obj.get("headers")
    if isinstance(headers, list) and headers:
        header_line = " | ".join(str(h).strip() for h in headers[:max_cols])
        if header_line.strip():
            rows.append(header_line)
    df = table_obj.get("pandas_df") or table_obj.get("pandas_df_raw") or []
    if not isinstance(df, list):
        return rows
    for row in df[:max_rows]:
        if isinstance(row, dict):
            cells = [str(row.get(k, "")) for k in row.keys()]
        elif isinstance(row, list):
            cells = [str(cell) for cell in row[:max_cols]]
        else:
            cells = [str(row)]
        line = " | ".join(cell.strip() for cell in cells if str(cell).strip())
        if not line:
            continue
        if len(line) > max_chars:
            line = line[: max(3, max_chars - 1)].rstrip() + "…"
        rows.append(line)
    return rows


def table_payload_from_obj(table_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Build payload dict for table overlay."""
    headers_preview = headers_preview_from_table(table_obj)
    rows_preview = rows_preview_from_table(table_obj)
    camelot_acc = None
    pandas_acc = None
    try:
        camelot_acc = float((table_obj.get("camelot_metrics", {}) or {}).get("accuracy"))
    except Exception:
        camelot_acc = table_obj.get("camelot_accuracy")
    try:
        pandas_acc = float((table_obj.get("pandas_metrics", {}) or {}).get("data_density"))
    except Exception:
        pandas_acc = table_obj.get("pandas_accuracy")

    payload = {
        "table_index": table_obj.get("table_index"),
        "title": table_obj.get("title"),
        "caption": table_obj.get("caption"),
        "headers_preview": headers_preview,
        "rows_preview": rows_preview,
        "camelot_accuracy": camelot_acc,
        "pandas_accuracy": pandas_acc,
    }
    if table_obj.get("normalized_id"):
        payload["normalized_id"] = table_obj.get("normalized_id")
    if table_obj.get("section_id"):
        payload["section_id"] = table_obj.get("section_id")
    return payload


__all__ = [
    "wrap_label_lines",
    "format_label",
    "stable_overlay_id",
    "headers_preview_from_table",
    "rows_preview_from_table",
    "table_payload_from_obj",
]
