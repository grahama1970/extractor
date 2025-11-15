#!/usr/bin/env python3
"""
Stage 09a: PDF Annotator (deterministic, no LLM)

Overlays rectangles for sections, tables, and figures on the clean PDF to aid
visual review and collaboration. Writes an annotated PDF and a JSON index of
all overlays for downstream tooling.

Enhancements:
- Stage-specific log sink (stage.log)
- Per-stage timings (timings.jsonl, timings_summary.json)
- Stable overlay IDs and richer annotations.json summary
- Optional true PDF annotations (commentable), with fallback to drawn rectangles
- Overlay toggles and label sizing; per-page PNG previews for quick review
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict

from loguru import logger
import fitz  # PyMuPDF
from extractor.pipeline.utils.step_sanity import run_step_sanity

# No CLI framework; import and call run(...)

STEP_NAME = "09a_pdf_annotator"


def sanity() -> int:
    return run_step_sanity(STEP_NAME)

# ---- Visual design ----------------------------------------------------------
# Stroke colors (0..1 RGB) chosen for readability & CVD safety.
COLORS: Dict[str, tuple[float, float, float]] = {
    "section": (0.051, 0.580, 0.533),       # #0D9488 teal-600
    "section_frame": (0.051, 0.580, 0.533),
    "text_chunk": (0.392, 0.455, 0.545),    # #64748B slate-500
    "reflow_paragraph": (0.392, 0.455, 0.545),
    "reflow_list": (0.392, 0.455, 0.545),
    "reflow_heading": (0.051, 0.580, 0.533),
    "figure": (0.145, 0.388, 0.922),        # #2563EB blue-600
    "reflow_figure": (0.145, 0.388, 0.922),
    "table": (0.863, 0.149, 0.149),         # #DC2626 red-600
    "reflow_table": (0.730, 0.100, 0.100),
    "table_merged": (0.730, 0.100, 0.100),  # darker red
    "requirement": (0.851, 0.467, 0.024),   # #D97706 amber-600
    "grid": (0.612, 0.639, 0.686),          # slate-400
    "columns": (0.055, 0.647, 0.655),       # teal-ish
    "header_candidate": (0.851, 0.024, 0.851),
    "table_rejected": (0.35, 0.35, 0.35),
}

# Light fills + opacities per kind (figure a bit stronger so watermark reads)
def _lighten(rgb, f=0.95):
    r, g, b = rgb
    return (1 - (1 - r) * f, 1 - (1 - g) * f, 1 - (1 - b) * f)

def _style_for_kind(kind: str) -> tuple[tuple[float, float, float], tuple[float, float, float], float]:
    stroke = COLORS.get(kind, (0.3, 0.3, 0.3))
    fill = _lighten(stroke, 0.95)
    opacity = 0.24 if kind == "figure" else 0.18
    return stroke, fill, opacity

# Human-friendly gutter labels
HUMAN_KIND = {
    "section": "Section Header",
    "reflow_heading": "Section Header",
    "reflow_paragraph": "Text Block",
    "reflow_list": "Text Block",
    "text_chunk": "Text Block",
    "figure": "Figure",
    "reflow_figure": "Figure",
    "table": "Table",
    "table_merged": "Table",
    "reflow_table": "Table",
    "requirement": "Requirement",
}

# Gutter lane + adornments
GUTTER_SIDE = "left"
GUTTER_WIDTH = 84.0
GUTTER_PAD = 8.0
PLAQUE_PAD_X = 6.0
PLAQUE_PAD_Y = 4.0
GUTTER_FILL = (0.76, 0.86, 0.96)
GUTTER_BORDER = (0.24, 0.44, 0.68)
PLAQUE_FILL = (0.97, 0.99, 1.0)
PLAQUE_BORDER = (0.62, 0.72, 0.84)
PLAQUE_FONT_MIN = 5.5

LABEL_MARGIN_PTS = 14.0
LABEL_MIN_FONT = 8
LABEL_BG = (1.0, 0.98, 0.85)
LABEL_TEXT_COLOR = (0.1, 0.1, 0.1)
TABLE_CALLOUT_BG = (0.98, 0.99, 0.92)
FIGURE_CALLOUT_BG = (0.94, 0.97, 1.0)
PREVIEW_DPI = 144
MAX_TABS_PER_PAGE = 12
TAB_GUTTER_WIDTH = 48.0
TAB_HEIGHT = 34.0
TAB_GAP = 6.0
TAB_COLORS = {
    "section": (0.82, 0.92, 0.82),
    "table": (0.95, 0.85, 0.85),
    "more": (0.9, 0.9, 0.9),
}


def _draw_page_gutter_side(page: fitz.Page, side: str = "left") -> fitz.Rect:
    """Return the gutter rect on the requested side (no fill/stroke)."""
    r = page.rect
    if side == "left":
        lane = fitz.Rect(r.x0 + 6, r.y0 + 6, r.x0 + 6 + GUTTER_WIDTH, r.y1 - 6)
    else:
        lane = fitz.Rect(r.x1 - 6 - GUTTER_WIDTH, r.y0 + 6, r.x1 - 6, r.y1 - 6)
    return lane

def _draw_page_gutter(page: fitz.Page) -> fitz.Rect:
    """Backward-compatible helper: draw using global GUTTER_SIDE."""
    return _draw_page_gutter_side(page, GUTTER_SIDE)


def _draw_gutter_tag(page: fitz.Page, lane: fitz.Rect, target: fitz.Rect, text: str, color=(0.12, 0.12, 0.12), font=9.0) -> None:
    if not text or lane is None:
        return
    t = text.strip()
    if not t:
        return
    txt_w = page.get_text_length(t, fontsize=font)
    max_w = max(12.0, lane.width - 2 * GUTTER_PAD)
    font_size = font
    iterations = 0
    while txt_w > max_w and font_size > PLAQUE_FONT_MIN:
        font_size -= 0.8
        txt_w = page.get_text_length(t, fontsize=font_size)
        iterations += 1
    if txt_w > max_w:
        while txt_w > max_w and len(t) > 3:
            t = t[:-1]
            txt_w = page.get_text_length(t + "…", fontsize=font_size)
        t = (t + "…") if len(t) > 3 else t
    plaque_h = font_size * 1.7
    cy = target.y0 + target.height / 2.0
    top = max(lane.y0 + GUTTER_PAD, min(cy - plaque_h / 2.0, lane.y1 - GUTTER_PAD - plaque_h))
    left = lane.x0 + GUTTER_PAD
    plaque_w = page.get_text_length(t, fontsize=font_size) + 2 * PLAQUE_PAD_X
    plaque = fitz.Rect(left, top, left + plaque_w, top + plaque_h)
    # Prefer FreeText annotations so downstream checks can detect and reason about plaques.
    # Fall back to a drawn rectangle + inserted text if annotations fail.
    try:
        annot = page.add_freetext_annot(
            plaque, t, fontsize=font_size, text_color=color, fill_color=PLAQUE_FILL
        )
        try:
            annot.set_border(width=0.6)
        except Exception:
            pass
        try:
            annot.set_colors(stroke=PLAQUE_BORDER)
        except Exception:
            pass
        try:
            annot.set_opacity(0.98)
        except Exception:
            pass
        annot.update()
    except Exception:
        page.draw_rect(plaque, fill=PLAQUE_FILL, color=PLAQUE_BORDER, width=0.6, overlay=True)
        page.insert_text(
            (plaque.x0 + PLAQUE_PAD_X, plaque.y0 + font_size * 1.2 - 1),
            t,
            fontsize=font_size,
            color=color,
            overlay=True,
        )
    p_from = fitz.Point(plaque.x1, plaque.y0 + plaque.height / 2.0)
    p_to = fitz.Point(target.x0, min(max(target.y0 + 4, p_from.y), target.y1 - 4))
    try:
        connector = page.add_line_annot(p_from, p_to)
        connector.set_colors(stroke=GUTTER_BORDER)
        connector.set_border(width=0.7)
        connector.update()
    except Exception:
        page.draw_line(p_from, p_to, color=GUTTER_BORDER, width=0.7)


def _draw_t_endcaps(page: fitz.Page, lane: fitz.Rect, y0: float, y1: float, color=(0.25, 0.25, 0.25)) -> None:
    if lane is None:
        return
    x = lane.x1 - 10.0
    try:
        vertical = page.add_line_annot(fitz.Point(x, y0), fitz.Point(x, y1))
        vertical.set_colors(stroke=color)
        vertical.set_border(width=1.0)
        vertical.update()
        top_bar = page.add_line_annot(fitz.Point(x - 6, y0), fitz.Point(x + 6, y0))
        top_bar.set_colors(stroke=color); top_bar.set_border(width=1.0); top_bar.update()
        bottom_bar = page.add_line_annot(fitz.Point(x - 6, y1), fitz.Point(x + 6, y1))
        bottom_bar.set_colors(stroke=color); bottom_bar.set_border(width=1.0); bottom_bar.update()
    except Exception:
        page.draw_line(fitz.Point(x, y0), fitz.Point(x, y1), color=color, width=1.0)
        page.draw_line(fitz.Point(x - 6, y0), fitz.Point(x + 6, y0), color=color, width=1.0)
        page.draw_line(fitz.Point(x - 6, y1), fitz.Point(x + 6, y1), color=color, width=1.0)


def _draw_section_title_plaque(page: fitz.Page, rect: fitz.Rect, text: str, stroke=(0.86, 0.25, 0.2), font=11.0) -> None:
    if not text:
        return
    t = text.strip()
    max_w = min(rect.width * 0.9, 360.0)
    while page.get_text_length(t, fontsize=font) > max_w and len(t) > 5:
        t = t[:-1]
    if t != text:
        t = t.rstrip(" .,;") + "…"
    h = font * 1.8
    top = max(page.rect.y0 + 6, rect.y0 - h - 6)
    left = rect.x0 + 6
    plaque = fitz.Rect(left, top, left + page.get_text_length(t, fontsize=font) + 2 * PLAQUE_PAD_X, top + h)
    page.draw_rect(plaque, fill=(1, 1, 1), color=stroke, width=0.9, overlay=True)
    page.insert_text((plaque.x0 + PLAQUE_PAD_X, plaque.y0 + font * 1.2 - 1), t, fontsize=font, color=stroke, overlay=True)


def _draw_figure_watermark(page: fitz.Page, rect: fitz.Rect, text: str) -> None:
    text = (text or "").strip()
    if not text:
        return
    font = max(10.0, rect.height * 0.06)
    max_width = max(60.0, rect.width - 24.0)
    lines = _wrap_label_lines(page, text, font, max_width, max_lines=6)
    if not lines:
        lines = [text[:80] + ("…" if len(text) > 80 else "")]
    line_height = font * 1.25
    box_height = line_height * len(lines) + 8
    box_width = max(fitz.get_text_length(max(lines, key=len), fontsize=font) + 12, max_width)
    box = fitz.Rect(
        rect.x0 + 12,
        rect.y0 + 12,
        min(rect.x0 + 12 + box_width, rect.x1 - 12),
        min(rect.y0 + 12 + box_height, rect.y1 - 12),
    )
    page.draw_rect(box, fill=(1.0, 1.0, 1.0), color=(0.7, 0.7, 0.7), width=0.6, overlay=True)
    page.insert_textbox(box, "\n".join(lines), fontsize=font, color=(0.25, 0.25, 0.25), lineheight=1.2, align=0, overlay=True)


def _draw_table_metrics(page: fitz.Page, rect: fitz.Rect, headers_preview: str | None, camelot_acc: float | None, pandas_acc: float | None, color=(0.0, 0.0, 0.0)) -> None:
    y = rect.y1 - 6
    x = rect.x0 + 8
    font1 = 9.5
    font2 = 9.0
    if headers_preview:
        page.insert_text((x, y - font1), f"Data: {headers_preview}", fontsize=font1, color=color, overlay=True)
        y -= font1 + 2
    metrics: list[str] = []
    if camelot_acc is not None:
        try:
            metrics.append(f"camelot={float(camelot_acc):.2f}")
        except Exception:
            pass
    if pandas_acc is not None:
        try:
            metrics.append(f"pandas={float(pandas_acc):.2f}")
        except Exception:
            pass
    page.insert_text((x, y - font2), f"Metrics: {', '.join(metrics) if metrics else '—'}", fontsize=font2, color=color, overlay=True)


def _headers_preview_from_table(table_obj: dict[str, Any], limit: int = 6) -> str | None:
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


def _rows_preview_from_table(table_obj: dict[str, Any], max_rows: int = 4, max_cols: int = 4, max_chars: int = 70) -> list[str]:
    rows: list[str] = []
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


def _table_payload_from_obj(table_obj: dict[str, Any]) -> dict[str, Any]:
    headers_preview = _headers_preview_from_table(table_obj)
    rows_preview = _rows_preview_from_table(table_obj)
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


def _draw_table_preview_box(page: fitz.Page, rect: fitz.Rect, lines: list[str], color=(0.0, 0.0, 0.0)) -> None:
    if not lines:
        return
    max_lines = min(len(lines), 6)
    panel_lines = ["Table preview:"] + [ln for ln in lines[:max_lines]]
    font = 8.4
    line_height = font * 1.25
    padding = 6.0
    box_height = line_height * len(panel_lines) + padding * 2
    panel_width = min(320.0, rect.width - 16.0)
    top = rect.y0 - box_height - 6
    if top < page.rect.y0 + 4:
        top = rect.y1 + 6
    if top + box_height > page.rect.y1 - 4:
        top = max(page.rect.y0 + 4, rect.y0 + 6)
    box = fitz.Rect(rect.x0 + 6, top, rect.x0 + 6 + panel_width, top + box_height)
    page.draw_rect(box, fill=TABLE_CALLOUT_BG, color=(0.65, 0.65, 0.65), width=0.6, overlay=True)
    preview_text = "\n".join(panel_lines)
    page.insert_textbox(box, preview_text, fontsize=font, color=color, lineheight=1.2, align=0, overlay=True)


def _draw_figure_caption_box(page: fitz.Page, rect: fitz.Rect, text: str) -> None:
    caption = (text or "").strip()
    if not caption:
        return
    font = 9.2
    line_height = font * 1.3
    max_width = min(340.0, rect.width - 12.0)
    lines = _wrap_label_lines(page, caption, font, max_width, max_lines=8)
    if not lines:
        lines = [caption[:120] + ("…" if len(caption) > 120 else "")]
    height = line_height * len(lines) + 10
    box = fitz.Rect(rect.x0 + 6, rect.y1 + 8, rect.x0 + 6 + max_width, rect.y1 + 8 + height)
    if box.y1 > page.rect.y1 - 4:
        box = fitz.Rect(rect.x0 + 6, max(rect.y0 - height - 8, page.rect.y0 + 6), rect.x0 + 6 + max_width, max(rect.y0 - 8, page.rect.y0 + 6) + height)
    page.draw_rect(box, fill=FIGURE_CALLOUT_BG, color=(0.5, 0.6, 0.8), width=0.6, overlay=True)
    panel = ["Figure description:"] + lines
    page.insert_textbox(box, "\n".join(panel), fontsize=font, color=(0.1, 0.14, 0.2), lineheight=1.2, align=0, overlay=True)


def _safe_get_bbox(obj: dict[str, Any]) -> list[float] | None:
    bb = obj.get("bbox") or obj.get("box")
    if not isinstance(bb, (list, tuple)) or len(bb) != 4:
        return None
    try:
        return [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])]
    except Exception:
        return None


def _rect_from_pdf_bbox(page: fitz.Page, bbox: list[float]) -> fitz.Rect:
    """Convert a PDF-space bbox (origin bottom-left) to a PyMuPDF rect (origin top-left)."""
    x0, y0, x1, y1 = bbox
    x_lo, x_hi = sorted((x0, x1))
    y_lo, y_hi = sorted((y0, y1))
    height = float(page.rect.height)
    top = height - y_hi
    bottom = height - y_lo
    # Clamp to the page bounds and ensure positive area
    rect = fitz.Rect(x_lo, top, x_hi, bottom)
    rect = rect & page.rect
    if rect.y1 < rect.y0:
        rect = fitz.Rect(rect.x0, rect.y1, rect.x1, rect.y0)
    if rect.width <= 0 or rect.height <= 0:
        # Expand minimally to avoid zero-area overlays
        rect = fitz.Rect(rect.x0, rect.y0, rect.x0 + max(1.0, rect.width), rect.y0 + max(1.0, rect.height)) & page.rect
    return rect


def _wrap_label_lines(page: fitz.Page, text: str, font: float, max_width: float, max_lines: int = 3) -> list[str]:
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
    lines: list[str] = []
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


def _format_label(kind: str, payload: dict[str, Any], override: str | None) -> str:
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
        if isinstance(pages, list) and pages:
            try:
                page_str = f" (pages {', '.join(str(int(p)) for p in pages)})"
            except Exception:
                page_str = f" (pages {', '.join(str(p) for p in pages)})"
        else:
            page_str = ""
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


def _stable_overlay_id(kind: str, page_index: int, payload: dict[str, Any], fallback: int) -> str:
    """Generate a stable identifier for an overlay based on its semantic identity."""
    page_token = f"@{page_index + 1}" if page_index >= 0 else ""

    def _first_str(keys: list[str]) -> str | None:
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


def _draw_label(
    page: fitz.Page,
    rect: fitz.Rect,
    text: str,
    color: tuple[float, float, float],
    font_size: float,
) -> None:
    try:
        if not text:
            return
        text = text.strip()
        if not text:
            return
        font = max(float(font_size), LABEL_MIN_FONT)
        line_height = font * 1.2
        y_center = rect.y0 + rect.height / 2.0
        left_space = rect.x0 - page.rect.x0
        right_space = page.rect.x1 - rect.x1

        def _draw_lines(x: float, top: float, width: float, lines: list[str]) -> fitz.Point:
            height = line_height * len(lines)
            bg = fitz.Rect(x - 2, top - 2, x + width + 2, top + height + 2)
            text_block = "\n".join(lines)
            try:
                annot = page.add_freetext_annot(
                    bg,
                    text_block,
                    fontsize=font,
                    text_color=LABEL_TEXT_COLOR,
                    fill_color=LABEL_BG,
                )
                try:
                    annot.set_border(width=0.4)
                    annot.set_colors(stroke=color)
                    annot.set_opacity(0.95)
                    annot.update()
                except Exception:
                    pass
            except Exception:
                page.draw_rect(bg, color=color, width=0.4, fill=LABEL_BG, overlay=False)
                y = top + font
                for ln in lines:
                    page.insert_text((x, y), ln, fontsize=font, color=LABEL_TEXT_COLOR, overlay=False)
                    y += line_height
            return fitz.Point(bg.x0 + width / 2.0, bg.y0 + height / 2.0)

        # Try left margin first
        avail_left = left_space - LABEL_MARGIN_PTS * 2
        if avail_left > font * 3:
            lines = _wrap_label_lines(page, text, font, avail_left)
            if lines:
                width = max(fitz.get_text_length(ln, fontsize=font) for ln in lines)
                if left_space >= width + LABEL_MARGIN_PTS * 2:
                    text_height = line_height * len(lines)
                    top = y_center - text_height / 2.0
                    top = max(page.rect.y0 + 2, min(page.rect.y1 - text_height - 2, top))
                    x = rect.x0 - LABEL_MARGIN_PTS - width
                    center = _draw_lines(x, top, width, lines)
                    end = fitz.Point(rect.x0, max(rect.y0, min(rect.y1, center.y)))
                    page.draw_line(center, end, color=color, width=0.4)
                    return

        # Try right margin
        avail_right = right_space - LABEL_MARGIN_PTS * 2
        if avail_right > font * 3:
            lines = _wrap_label_lines(page, text, font, avail_right)
            if lines:
                width = max(fitz.get_text_length(ln, fontsize=font) for ln in lines)
                if right_space >= width + LABEL_MARGIN_PTS * 2:
                    text_height = line_height * len(lines)
                    top = y_center - text_height / 2.0
                    top = max(page.rect.y0 + 2, min(page.rect.y1 - text_height - 2, top))
                    x = rect.x1 + LABEL_MARGIN_PTS
                    center = _draw_lines(x, top, width, lines)
                    end = fitz.Point(rect.x1, max(rect.y0, min(rect.y1, center.y)))
                    page.draw_line(end, center, color=color, width=0.4)
                    return

        # Fallback above/below
        max_available = min(page.rect.width - LABEL_MARGIN_PTS * 2, max(rect.width, font * 6))
        lines = _wrap_label_lines(page, text, font, max_available)
        if not lines:
            return
        width = max(fitz.get_text_length(ln, fontsize=font) for ln in lines)
        text_height = line_height * len(lines)
        top = rect.y0 - LABEL_MARGIN_PTS - text_height
        if top >= page.rect.y0 + 2:
            x = max(page.rect.x0 + LABEL_MARGIN_PTS, min(rect.x0, page.rect.x1 - width - LABEL_MARGIN_PTS))
            center = _draw_lines(x, top, width, lines)
            end = fitz.Point(rect.x0 + rect.width / 2.0, rect.y0)
            page.draw_line(center, end, color=color, width=0.4)
            return
        top = rect.y1 + LABEL_MARGIN_PTS
        if top + text_height > page.rect.y1 - 2:
            top = page.rect.y1 - text_height - 2
        x = max(page.rect.x0 + LABEL_MARGIN_PTS, min(rect.x0, page.rect.x1 - width - LABEL_MARGIN_PTS))
        center = _draw_lines(x, top, width, lines)
        end = fitz.Point(rect.x0 + rect.width / 2.0, rect.y1)
        page.draw_line(end, center, color=color, width=0.4)
    except Exception:
        pass


def _collect_tabs(sections: list[dict[str, Any]], overlays: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tabs: list[dict[str, Any]] = []
    section_index: dict[str, dict[str, Any]] = {}
    for s in sections:
        sid_raw = s.get("id") or s.get("section_id")
        sid = str(sid_raw) if sid_raw is not None else None
        if not sid:
            continue
        base_page = _coerce_page(s.get("page_start"), s.get("page_idx"), s.get("page"))
        if base_page is None:
            continue
        metadata = s.get("metadata") or {}
        continued = metadata.get("continued_pages") or []
        pages = {int(base_page)}
        for p in continued:
            pg = _coerce_page(p)
            if pg is not None:
                pages.add(int(pg))
        section = section_index.setdefault(
            sid,
            {
                "key": f"SEC::{sid}",
                "label": s.get("title") or s.get("display_title") or sid,
                "kind": "section",
                "pages": set(),
            },
        )
        section["pages"].update(pages)
    for section in section_index.values():
        section["pages"] = sorted(section["pages"])
        section["primary_page"] = section["pages"][0] if section["pages"] else 0
        section["stable_id"] = f"{section['key']}@{section['primary_page'] + 1}" if section["pages"] else section["key"]
        tabs.append(section)

    merged_groups: dict[str, dict[str, Any]] = {}
    for o in overlays:
        if o.get("kind") != "table_merged":
            continue
        key_raw = o.get("logical_table_key") or o.get("group")
        key = str(key_raw) if key_raw is not None else None
        if not key:
            continue
        group = merged_groups.setdefault(
            key,
            {
                "key": f"TBL::{key}",
                "label": o.get("_label") or f"Table {key}",
                "kind": "table",
                "pages": set(),
            },
        )
        group["pages"].add(int(o.get("page", 0)))
        extra = o.get("pages_in_group") or []
        if isinstance(extra, list):
            for p in extra:
                try:
                    pg = int(p) - 1
                except Exception:
                    pg = _coerce_page(p)
                if pg is not None:
                    group["pages"].add(int(pg))
    for group in merged_groups.values():
        group["pages"] = sorted(group["pages"])
        if not group["pages"]:
            continue
        group["primary_page"] = group["pages"][0]
        group["stable_id"] = f"{group['key']}@{group['primary_page'] + 1}"
        tabs.append(group)

    tabs.sort(key=lambda t: (t.get("primary_page", 0), 0 if t.get("kind") == "section" else 1, t.get("label", "")))
    for idx, tab in enumerate(tabs):
        tab["_rank"] = idx
    return tabs


def _draw_vertical_tabs(
    doc: fitz.Document,
    tabs: list[dict[str, Any]],
    *,
    side: str = "right",
    gutter_w: float = TAB_GUTTER_WIDTH,
    tab_h: float = TAB_HEIGHT,
    tab_gap: float = TAB_GAP,
    max_tabs_per_page: int = MAX_TABS_PER_PAGE,
) -> dict[str, Any]:
    summary = {
        "mode": "none",
        "sections": 0,
        "tables": 0,
        "total": 0,
        "pages_overflow_initial": [],
        "pages_overflow": [],
        "downgraded": False,
    }
    if not tabs:
        return summary

    def _build_per_page(candidates: list[dict[str, Any]]) -> defaultdict[int, list[dict[str, Any]]]:
        mapping: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
        for tab in candidates:
            for pg in tab.get("pages", []):
                if 0 <= pg < len(doc):
                    mapping[pg].append(tab)
        return mapping

    per_page_all = _build_per_page(tabs)
    overflow_initial = sorted(pg for pg, lst in per_page_all.items() if len(lst) > max_tabs_per_page)
    use_tabs = tabs
    downgraded = False
    if overflow_initial and any(tab.get("kind") == "table" for tab in tabs):
        use_tabs = [tab for tab in tabs if tab.get("kind") == "section"]
        per_page_all = _build_per_page(use_tabs)
        downgraded = True
        if downgraded:
            logger.info(
                "09a tabs: downgraded to sections_only due to overflow on pages %s",
                overflow_initial,
            )
    per_page = per_page_all
    overflow_after = sorted(pg for pg, lst in per_page.items() if len(lst) > max_tabs_per_page)

    summary.update(
        {
            "mode": "both" if not downgraded and any(tab.get("kind") == "table" for tab in tabs) else ("sections_only" if use_tabs else "none"),
            "sections": sum(1 for tab in use_tabs if tab.get("kind") == "section"),
            "tables": sum(1 for tab in use_tabs if tab.get("kind") == "table"),
            "total": len(use_tabs),
            "pages_overflow_initial": overflow_initial,
            "pages_overflow": overflow_after,
            "downgraded": downgraded,
        }
    )

    for pno, tab_list in per_page.items():
        if not tab_list:
            continue
        page = doc[pno]
        rect = page.rect
        if side == "right":
            gutter = fitz.Rect(rect.x1 - gutter_w, rect.y0, rect.x1, rect.y1)
            offset = rect.x1 - gutter_w
            rotate = 90
        else:
            gutter = fitz.Rect(rect.x0, rect.y0, rect.x0 + gutter_w, rect.y1)
            offset = rect.x0
            rotate = 270
        page.draw_rect(gutter, fill=(0.96, 0.96, 0.96), color=None, width=0)
        ordered = sorted(
            tab_list,
            key=lambda t: (0 if t.get("kind") == "section" else 1, t.get("_rank", 0)),
        )
        display_tabs = ordered[: max_tabs_per_page]
        overflow = len(ordered) > max_tabs_per_page
        if overflow and display_tabs:
            target = ordered[max_tabs_per_page - 1].get("primary_page", pno)
            display_tabs = ordered[: max_tabs_per_page - 1] + [
                {
                    "key": f"MORE::{pno}",
                    "label": "⋯ More",
                    "kind": "more",
                    "pages": [pno],
                    "primary_page": target,
                    "_rank": 10_000,
                }
            ]
        y = 24.0
        for tab in display_tabs:
            tab_rect = fitz.Rect(0, y, gutter_w, y + tab_h)
            tab_rect = tab_rect + (offset, 0, offset, 0)
            y += tab_h + tab_gap
            color = TAB_COLORS.get(tab.get("kind"), (0.85, 0.85, 0.85))
            page.draw_rect(tab_rect, fill=color, color=None, width=0)
            label = tab.get("label") or tab.get("key")
            if pno not in (tab.get("pages") or []):
                text = label
            elif pno != tab.get("primary_page"):
                text = f"{label} (cont.)"
            else:
                text = label
            page.insert_textbox(
                tab_rect,
                text[:64],
                fontsize=9,
                fontname="helv",
                color=LABEL_TEXT_COLOR,
                rotate=rotate,
                align=1,
            )
            try:
                page.insert_link(
                    {
                        "kind": fitz.LINK_GOTO,
                        "from": tab_rect,
                        "page": int(tab.get("primary_page", pno)),
                        "zoom": 0,
                    }
                )
            except Exception:
                continue

    return summary


def _emit_overlay_map(stage_dir: Path, overlays: list[dict[str, Any]], pages_touched: set[int], dpi: int = PREVIEW_DPI) -> None:
    vis_dir = stage_dir / "visual_output"
    vis_dir.mkdir(parents=True, exist_ok=True)
    scale = dpi / 72.0
    by_page: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    for ov in overlays:
        by_page[int(ov.get("page", 0))].append(ov)
    payload = {"dpi": dpi, "pages": []}
    page_keys = sorted({int(p) for p in pages_touched} | set(by_page.keys()))
    for pg in page_keys:
        overlays_px = []
        for ov in by_page.get(pg, []):
            rb = ov.get("render_bbox") or ov.get("bbox") or [0, 0, 0, 0]
            x0, y0, x1, y1 = rb
            meta = {k: v for k, v in ov.items() if k not in {"bbox", "render_bbox", "page", "kind", "_label"}}
            meta.setdefault("_label", ov.get("_label"))
            overlays_px.append(
                {
                    "id": ov.get("stable_id") or f"ov{ov.get('overlay_id')}",
                    "kind": ov.get("kind"),
                    "label": ov.get("_label"),
                    "meta": meta,
                    "px_rect": [x0 * scale, y0 * scale, x1 * scale, y1 * scale],
                }
            )
        payload["pages"].append(
            {
                "index": pg,
                "image": f"page_{pg+1:04d}.png",
                "overlays": overlays_px,
            }
        )
    (vis_dir / "overlay_map.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    comments_path = vis_dir / "comments.jsonl"
    if not comments_path.exists():
        comments_path.write_text("", encoding="utf-8")

def _coerce_page(*values: Any) -> int | None:
    """Return the first non-None value coerced to int, allowing zero."""
    for value in values:
        if value is None:
            continue
        try:
            return int(value)
        except Exception:
            continue
    return None


def _write_artifacts_index(stage_dir: Path) -> None:
    try:
        json_dir = stage_dir / "json_output"
        vis_dir = stage_dir / "visual_output"
        idx = {
            "pdf": [str((stage_dir / "annotated.pdf").name)],
            "json": [p.name for p in (json_dir.glob("*.json"))] if json_dir.exists() else [],
            "previews": [p.name for p in (vis_dir.glob("*.png"))] if vis_dir.exists() else [],
            "logs": ["stage.log"],
        }
        (json_dir / "artifacts_index.json").write_text(json.dumps(idx, indent=2))
    except Exception:
        pass


def _append_timing(logs_dir: Path, record: Dict[str, Any]) -> None:
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        with (logs_dir / "timings.jsonl").open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record) + "\n")
    except Exception:
        pass


def _summarize_timings(logs_dir: Path) -> None:
    try:
        tfile = logs_dir / "timings.jsonl"
        if not tfile.exists():
            return
        lat = []
        count = 0
        for line in tfile.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                if rec.get("latency_ms") is not None:
                    lat.append(float(rec["latency_ms"]))
                count += 1
            except Exception:
                continue
        lat.sort()
        def _pct(p: float) -> float:
            if not lat:
                return 0.0
            idx = int(max(0, min(len(lat) - 1, round(p * (len(lat) - 1)))))
            return float(lat[idx])
        summary = {"events": count, "p50_ms": _pct(0.50), "p95_ms": _pct(0.95)}
        (logs_dir / "timings_summary.json").write_text(json.dumps(summary, indent=2))
    except Exception:
        pass


def run(
    pdf_path: Path,
    sections_json: Path,
    tables_json: Path,
    figures_json: Path,
    reflowed_json: Path | None = None,
    blocks02_json: Path | None = None,
    headers03_json: Path | None = None,
    layout06b_json: Path | None = None,
    output_dir: Path = Path("data/results/pipeline"),
    stage_tag: str = "auto",
    labels: bool = True,
    grid: int = 0,
    rewrite_headers: bool = False,
    overwrite_pdf: bool = False,
    replace_text_layer: bool = False,
    *,
    # New optional knobs (kw-only to preserve current callers)
    draw_sections: bool = True,
    prefer_reflow_sections: bool = True,
    draw_tables: bool = True,
    prefer_reflow_tables: bool = True,
    draw_figures: bool = True,
    draw_text_chunks: bool = True,
    draw_headers03: bool = True,
    draw_columns06b: bool = True,
    draw_grid: bool = False,
    label_font_size: int = 12,
    stroke_width: float = 1.0,
    pdf_annotations: bool = True,
    render_previews: bool = True,
    # NEW: visual simplifications for quick debugging
    draw_gutter: bool = True,
    # Dual-gutter controls: left shows element kinds; right shows section T endcaps
    gutter_left_tags: bool = True,
    gutter_right_section_caps: bool = True,
    draw_section_plaques: bool = True,
    draw_figure_watermark: bool = True,
    draw_table_callouts: bool = True,
    labels_verbose: bool = False,
    mode: str = "all",            # "structure" | "tables" | "reflow" | "all"
    max_text_overlays_per_page: int = 64,
) -> Path:
    # Decide stage directory name. Prefer running after 07/08/09 when reflowed_json is available.
    tag = stage_tag
    if tag == "auto":
        tag = "09a" if reflowed_json is not None else "06c"
    stage_dir = output_dir / f"{tag}_pdf_annotator"
    stage_dir.mkdir(parents=True, exist_ok=True)
    json_dir = stage_dir / "json_output"
    json_dir.mkdir(exist_ok=True)
    logs_dir = stage_dir / "logs"
    vis_dir = stage_dir / "visual_output"
    vis_dir.mkdir(parents=True, exist_ok=True)

    # Stage-specific log sink
    sink_id = None
    try:
        sink_id = logger.add(
            str(stage_dir / "stage.log"),
            level="INFO",
            enqueue=True,
            backtrace=False,
            diagnose=False,
            rotation="5 MB",
            retention=5,
        )
    except Exception:
        sink_id = None

    t0 = time.time()
    logger.info(f"09a_pdf_annotator: start → {pdf_path}")

    # Load inputs
    sections = (json.loads(sections_json.read_text(encoding="utf-8")).get("sections") or [])
    tables = (json.loads(tables_json.read_text(encoding="utf-8")).get("tables") or [])
    figures = (json.loads(figures_json.read_text(encoding="utf-8")).get("figures") or [])
    # Map figure_id -> ai_description (if present)
    fig_desc: dict[str, str] = {}
    for f in figures:
        try:
            fid = str(f.get("figure_id")) if f.get("figure_id") is not None else None
            desc = f.get("ai_description") or f.get("description") or ""
            if fid and isinstance(desc, str) and desc.strip():
                fig_desc[fid] = desc.strip()
        except Exception:
            continue
    reflowed_sections = []
    if reflowed_json is not None:
        try:
            rj = json.loads(reflowed_json.read_text(encoding="utf-8"))
            reflowed_sections = rj.get("reflowed_sections") or rj.get("sections") or []
        except Exception as e:
            logger.warning(f"Failed to read reflowed JSON: {e}")
    # Build block lookup for Stage 02 blocks: id -> (page, bbox)
    block_lookup = {}
    if blocks02_json is not None:
        try:
            b02 = json.loads(blocks02_json.read_text(encoding="utf-8"))
            blist = b02.get("blocks") or []
            for b in blist:
                try:
                    bid = b.get("id") or b.get("block_id")
                    bb = _safe_get_bbox(b)
                    pg = b.get("page") if b.get("page") is not None else b.get("page_idx")
                    if bid is not None and bb is not None and pg is not None:
                        block_lookup[str(bid)] = (int(pg), [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])])
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Failed to read blocks02 JSON: {e}")

    section_header_blocks: dict[str, dict[str, Any]] = {}
    for sec in sections:
        sid = sec.get("id") or sec.get("section_id") or sec.get("sectionId")
        if sid is None:
            continue
        sid_str = str(sid)
        for blk in sec.get("blocks") or []:
            btype = (blk.get("block_type") or blk.get("type") or "").lower()
            if btype == "sectionheader":
                section_header_blocks[sid_str] = blk
                break

    # Stage 03 suspicious headers (optional)
    headers03: list[dict[str, Any]] = []
    if headers03_json is None:
        # auto-discover under results dir when present
        auto = output_dir / "03_suspicious_headers" / "json_output" / "03_verified_blocks.json"
        if auto.exists():
            headers03_json = auto
    if headers03_json is not None and Path(headers03_json).exists():
        try:
            h03 = json.loads(Path(headers03_json).read_text(encoding="utf-8"))
            headers03 = h03.get("blocks") or []
        except Exception as e:
            logger.warning(f"Failed to read headers03 JSON: {e}")

    # Stage 06b layout sketch (optional)
    layout06b: dict[str, Any] | None = None
    if layout06b_json is None:
        auto = output_dir / "06b_layout_sketcher" / "json_output" / "06b_layout_sketch.json"
        if auto.exists():
            layout06b_json = auto
    if layout06b_json is not None and Path(layout06b_json).exists():
        try:
            layout06b = json.loads(Path(layout06b_json).read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to read layout06b JSON: {e}")

    # Optional: requirements overlays (Stage 07 requirements miner)
    requirements: list[dict[str, Any]] = []
    try:
        req_p = output_dir / "07_requirements_miner" / "json_output" / "07_requirements.json"
        if req_p.exists():
            req_obj = json.loads(req_p.read_text(encoding="utf-8"))
            requirements = req_obj.get("requirements") or []
    except Exception:
        requirements = []

    # Annotate
    # Safety: do not allow overwriting PDFs under data/input/ or external input paths
    if overwrite_pdf and str(pdf_path).startswith("data/input/"):
        raise ValueError("Refusing to overwrite a source PDF under data/input/. Use a copy or disable --overwrite-pdf.")
    doc = fitz.open(str(pdf_path))

    lane_left_by_page: dict[int, fitz.Rect] = {}
    lane_right_by_page: dict[int, fitz.Rect] = {}
    if draw_gutter:
        try:
            for pidx in range(len(doc)):
                try:
                    page = doc[pidx]
                except Exception:
                    continue
                if gutter_left_tags:
                    lane_left_by_page[pidx] = _draw_page_gutter_side(page, "left")
                if gutter_right_section_caps:
                    lane_right_by_page[pidx] = _draw_page_gutter_side(page, "right")
        except Exception as e:
            logger.warning(f"Failed to prepare gutter lanes: {e}")

    # Optional: mode presets (cheap switch for QA)
    try:
        m = (mode or "structure").lower().strip()
        if m == "structure":
            draw_text_chunks = False
            draw_headers03 = False
        elif m == "tables":
            draw_sections = False; draw_figures = False
            draw_text_chunks = False; draw_headers03 = False
        elif m == "reflow":
            draw_sections = False; draw_tables = False; draw_figures = False
        elif m == "all":
            pass
    except Exception:
        pass

    # Queue of gutter plaques to render in a final pass (after overlays/grid)
    # {_pg -> [ { "rect": fitz.Rect, "label": str, "color": (r,g,b) }, ... ]}
    pending_left_tags: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    pending_right_tags: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    overlays: list[dict[str, Any]] = []
    overlay_id = 0
    pages_touched: set[int] = set()

    def _normalized_page_index(idx: Any) -> int | None:
        _pg = _coerce_page(idx)
        if _pg is None:
            return None
        if _pg >= len(doc) and (_pg - 1) in range(len(doc)):
            _pg -= 1
        if _pg < 0 or _pg >= len(doc):
            return None
        return _pg

    def _color_for_kind(kind: str) -> tuple[float, float, float]:
        return COLORS.get(kind, (0.3, 0.3, 0.3))

    def _add(
        page_idx: int,
        bbox: list[float] | None,
        kind: str,
        payload: dict[str, Any],
        *,
        source_stage: str,
        source_ids: list[str] | None = None,
        label_text: str | None = None,
    ) -> None:
        nonlocal overlay_id
        _pg = _normalized_page_index(page_idx)
        if _pg is None:
            logger.warning(f"Skipping overlay (kind={kind}): out-of-range page {page_idx}")
            return
        page = doc[_pg]
        # Normalize bbox values and clamp to page rect
        if not bbox or not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            logger.warning(f"Skipping overlay (kind={kind}): invalid bbox {bbox}")
            return
        try:
            x0, y0, x1, y1 = [float(v) for v in bbox]
        except Exception:
            logger.warning(f"Skipping overlay (kind={kind}): non-numeric bbox {bbox}")
            return
        pdf_bbox = [x0, y0, x1, y1]
        rect = _rect_from_pdf_bbox(page, pdf_bbox)
        stroke_color, fill_color, fill_opacity = _style_for_kind(kind)
        label = _format_label(kind, payload, label_text)
        drew = False
        if pdf_annotations:
            try:
                annot = page.add_rect_annot(rect)
                annot.set_colors(stroke=stroke_color, fill=fill_color)
                try:
                    annot.set_border(width=max(1.2, float(stroke_width)))
                except Exception:
                    pass
                try:
                    annot.set_opacity(fill_opacity)
                except Exception:
                    pass
                try:
                    info = {}
                    if label:
                        info["title"] = str(label)[:120]
                    annot.set_info(info)
                except Exception:
                    pass
                # Store compact JSON payload in comment for quick inspection
                try:
                    compact = json.dumps({k: v for k, v in payload.items() if k not in {"bbox"}}, ensure_ascii=False)
                    annot.set_contents(compact[:2000])
                except Exception:
                    pass
                annot.update()
                drew = True
            except Exception:
                drew = False
        if not drew:
            try:
                page.draw_rect(rect, color=stroke_color, width=max(1.2, float(stroke_width)), fill=fill_color, overlay=True)
            except Exception:
                pass
        try:
            if draw_gutter:
                gutter_label = (label or HUMAN_KIND.get(kind) or "").strip()
                if gutter_left_tags and gutter_label and rect and lane_left_by_page.get(_pg):
                    pending_left_tags[_pg].append(
                        {"rect": rect, "label": gutter_label, "color": (0.12, 0.12, 0.12), "font": 9.0}
                    )
                if gutter_right_section_caps and kind == "section" and rect:
                    pending_right_tags[_pg].append((rect.y0, rect.y1))
            if kind == "section" and draw_section_plaques:
                _draw_section_title_plaque(page, rect, payload.get("title") or label, stroke=COLORS.get("table", (0.86, 0.25, 0.2)), font=11.0)
            if kind == "figure":
                desc = payload.get("ai_description") or payload.get("description") or payload.get("title")
                if draw_figure_watermark:
                    _draw_figure_watermark(page, rect, desc or "LLM description unavailable")
                _draw_figure_caption_box(page, rect, desc or "LLM description unavailable")
            if kind in ("table", "table_merged") and draw_table_callouts:
                _draw_table_metrics(
                    page,
                    rect,
                    headers_preview=payload.get("headers_preview"),
                    camelot_acc=payload.get("camelot_accuracy"),
                    pandas_acc=payload.get("pandas_accuracy"),
                    color=(0, 0, 0),
                )
                _draw_table_preview_box(page, rect, payload.get("rows_preview") or [])
        except Exception:
            pass
        if labels and labels_verbose and label:
            _draw_label(page, rect, label, stroke_color, float(label_font_size))
        payload_copy = dict(payload)
        if label:
            payload_copy.setdefault("_label", label)
        payload_copy.setdefault("pdf_bbox", pdf_bbox)
        render_bbox = [rect.x0, rect.y0, rect.x1, rect.y1]
        stable_id = _stable_overlay_id(kind, _pg, payload_copy, overlay_id)
        cleaned_source_ids: list[str] = []
        for sid in list(source_ids or []):
            if not sid:
                continue
            sid_str = str(sid)
            if sid_str not in cleaned_source_ids:
                cleaned_source_ids.append(sid_str)
        overlays.append(
            {
                "overlay_id": overlay_id,
                "page": _pg,
                "bbox": pdf_bbox,
                "render_bbox": render_bbox,
                "kind": kind,
                "stable_id": stable_id,
                "source_stage": source_stage,
                "source_ids": cleaned_source_ids,
                **payload_copy,
            }
        )
        overlay_id += 1
        pages_touched.add(_pg)

    # Sections (precise headers preferred)
    if draw_sections:
        t_s = time.monotonic()
        drew = 0
        missing_sections: list[dict[str, Any]] = []
        for sec in sections:
            sid = sec.get("id") or sec.get("section_id") or sec.get("sectionId")
            if sid is None:
                continue
            sid_str = str(sid)
            header_blk = section_header_blocks.get(sid_str)
            if header_blk:
                pg = _coerce_page(header_blk.get("page_idx"), header_blk.get("page"))
                bb = _safe_get_bbox(header_blk)
                if bb is not None and pg is not None:
                    payload = {"id": sid_str, "title": sec.get("title")}
                    _add(
                        pg,
                        bb,
                        "section",
                        payload,
                        source_stage="04_section_builder",
                        source_ids=[f"section_id:{sid_str}"],
                    )
                    drew += 1
                else:
                    missing_sections.append(sec)
            else:
                missing_sections.append(sec)
        if missing_sections and prefer_reflow_sections and reflowed_sections and block_lookup:
            for s in reflowed_sections:
                sid = s.get("id") or s.get("section_id") or s.get("sectionId")
                if sid is None:
                    continue
                sid_str = str(sid)
                if sid_str in section_header_blocks:
                    continue
                blocks = (s.get("reflowed_json", {}) or {}).get("blocks", [])
                per_page: dict[int, list[list[float]]] = {}
                for blk in blocks:
                    btype = (blk.get("type") or blk.get("block_type") or "").lower()
                    if btype == "figure":
                        continue
                    bids = ((blk.get("source") or {}).get("block_ids") or [])
                    for bid in bids:
                        lookup = block_lookup.get(str(bid))
                        if not lookup:
                            continue
                        pg, bb = lookup
                        per_page.setdefault(pg, []).append(bb)
                for pg, bbs in per_page.items():
                    if not bbs:
                        continue
                    x0 = min(bb[0] for bb in bbs); y0 = min(bb[1] for bb in bbs)
                    x1 = max(bb[2] for bb in bbs); y1 = max(bb[3] for bb in bbs)
                    payload = {"id": sid_str, "title": s.get("title"), "continuation": True}
                    _add(
                        pg,
                        [x0, y0, x1, y1],
                        "section",
                        payload,
                        source_stage="07_reflow_section",
                        source_ids=[f"section_id:{sid_str}"],
                    )
                    drew += 1
        if drew == 0:
            logger.warning("09a: no section overlays drawn (check section headers in Stage 04 output)")
        _append_timing(logs_dir, {"stage": "09a_pdf_annotator", "event": "draw_sections", "latency_ms": int((time.monotonic()-t_s)*1000)})

    # Tables (prefer logical merged tables from reflow when available)
    if draw_tables:
        t_s = time.monotonic()
        drew = 0
        merged_groups = 0
        if prefer_reflow_tables and reflowed_sections:
            groups: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
            for sec in reflowed_sections:
                sid = sec.get("id") or sec.get("section_id")
                for tbl in (sec.get("tables") or []):
                    lid = tbl.get("normalized_id") or tbl.get("logical_table_id")
                    title = (tbl.get("title") or tbl.get("caption") or "").strip().lower()
                    key = lid or f"section:{sid}::table:{tbl.get('table_index') or title or len(groups)}"
                    groups.setdefault(key, []).append((sec, tbl))
            for gkey, entries in groups.items():
                if not entries:
                    continue
                page_list: list[int] = []
                for _, tbl in entries:
                    pg = _coerce_page(
                        tbl.get("page_index"),
                        tbl.get("page_idx"),
                        tbl.get("page"),
                        (tbl.get("page_number") or 1) - 1,
                    )
                    if pg is not None:
                        page_list.append(pg)
                if not page_list:
                    continue
                sorted_pages = sorted(set(page_list))
                is_contiguous = len(sorted_pages) > 1 and sorted_pages == list(range(sorted_pages[0], sorted_pages[-1] + 1))
                kind = "table_merged" if is_contiguous else "table"
                if kind == "table_merged":
                    merged_groups += 1
                for sec, tbl in entries:
                    pg = _coerce_page(
                        tbl.get("page_index"),
                        tbl.get("page_idx"),
                        tbl.get("page"),
                        (tbl.get("page_number") or 1) - 1,
                    )
                    bb = _safe_get_bbox(tbl)
                    if pg is None or bb is None:
                        continue
                    payload = _table_payload_from_obj(tbl)
                    payload["section_id"] = sec.get("id") or payload.get("section_id")
                    if kind == "table_merged":
                        payload["logical_table_key"] = gkey
                        payload["pages_in_group"] = [int(p) + 1 for p in sorted_pages]
                    source_ids = []
                    if payload.get("table_index") is not None:
                        source_ids.append(f"table_index:{payload['table_index']}")
                    if payload.get("logical_table_key"):
                        source_ids.append(f"logical_table_key:{payload['logical_table_key']}")
                    _add(
                        pg,
                        bb,
                        kind,
                        payload,
                        source_stage="07_reflow_section",
                        source_ids=source_ids,
                    )
                    drew += 1
        if drew == 0:
            # Fallback to raw tables
            for t in tables:
                pg = _coerce_page(t.get("page_index"), t.get("page_idx"), t.get("page"))
                bb = _safe_get_bbox(t)
                if bb is not None and pg is not None:
                    payload = _table_payload_from_obj(t)
                    source_ids = []
                    idx_val = payload.get("table_index")
                    if idx_val is not None:
                        source_ids.append(f"table_index:{idx_val}")
                    _add(
                        pg,
                        bb,
                        "table",
                        payload,
                        source_stage="05_table_extractor",
                        source_ids=source_ids,
                    )
                    drew += 1
        if merged_groups == 0:
            # Fallback (also applicable in addition to raw table overlays):
            # use 06b sketch_v2 logical_table_id groups to draw merged overlays
            try:
                layout_dir = Path(layout06b_json).parent if isinstance(layout06b_json, Path) else None
                v2_path = (layout_dir / "06b_layout_sketch_v2.json") if (layout_dir and (layout_dir / "06b_layout_sketch_v2.json").exists()) else None
                tables_v2 = []
                if v2_path:
                    v2 = json.loads(v2_path.read_text(encoding="utf-8"))
                    for _sid, sv2 in (v2.get("sections") or {}).items():
                        for obj in (sv2.get("objects") or []):
                            if obj.get("type") == "table":
                                tables_v2.append(obj)
                else:
                    # fall back to per-section sketch_v2 in layout06b
                    secs = (layout06b.get("sections") or {}) if isinstance(layout06b, dict) else {}
                    for _sid, _sk in secs.items():
                        sv2 = (_sk.get("sketch_v2") or {}) if isinstance(_sk, dict) else {}
                        for obj in (sv2.get("objects") or []):
                            if obj.get("type") == "table":
                                tables_v2.append(obj)
                # group by lid
                by_lid = {}
                for o in tables_v2:
                    lid = o.get("logical_table_id")
                    if not lid:
                        continue
                    by_lid.setdefault(lid, []).append(o)
                for lid, items in by_lid.items():
                    pages = sorted({p for p in (_coerce_page(i.get("page_index"), i.get("page")) for i in items) if p is not None})
                    if len(pages) <= 1:
                        continue
                    if pages != list(range(pages[0], pages[-1] + 1)):
                        continue
                    for p in pages:
                        bbs = [i.get("bbox") for i in items if _coerce_page(i.get("page_index"), i.get("page")) == p]
                        bbs = [bb for bb in bbs if isinstance(bb, (list,tuple)) and len(bb)==4]
                        if not bbs:
                            continue
                        x0=min(bb[0] for bb in bbs); y0=min(bb[1] for bb in bbs)
                        x1=max(bb[2] for bb in bbs); y1=max(bb[3] for bb in bbs)
                        payload = {
                            "logical_table_key": lid,
                            "pages_in_group": [pp + 1 for pp in pages],
                        }
                        ltk = payload.get("logical_table_key")
                        source_ids = [f"logical_table_key:{ltk}"] if ltk else []
                        _add(
                            p,
                            [x0, y0, x1, y1],
                            "table_merged",
                            payload,
                            source_stage="06b_layout_sketcher",
                            source_ids=source_ids,
                        )
                        drew += 1
                merged_groups = sum(1 for lid, arr in by_lid.items() if len({p for p in (_coerce_page(i.get("page_index"), i.get("page")) for i in arr) if p is not None})>1)
                # If still no groups, derive header→body by header_norm non-digit + same cols and horizontal alignment
                if merged_groups == 0 and tables_v2:
                    # index by page
                    by_page: dict[int, list[dict[str, Any]]] = {}
                    for o in tables_v2:
                        p = _coerce_page(o.get("page_index"), o.get("page"))
                        by_page.setdefault(p, []).append(o)
                    def _is_generic(h: str) -> bool:
                        return bool(h) and all(tok.isdigit() for tok in h.split('|'))
                    def _h_iou(a, b):
                        try:
                            ax0,_,ax1,_ = a; bx0,_,bx1,_ = b
                            inter = max(0.0, min(ax1,bx1)-max(ax0,bx0))
                            uni = max(ax1,bx1)-min(ax0,bx0)
                            return float(inter/uni) if uni>0 else 0.0
                        except Exception:
                            return 0.0
                    for p, hdrs in by_page.items():
                        nxt = by_page.get(p+1) or []
                        for h in hdrs:
                            hn = (h.get('header_norm') or '').strip()
                            if not hn or _is_generic(hn):
                                continue
                            cols_h = int(h.get('cols') or 0)
                            for b in nxt:
                                cols_b = int(b.get('cols') or 0)
                                if cols_b != cols_h:
                                    continue
                                if _h_iou(h.get('bbox') or [0,0,0,0], b.get('bbox') or [0,0,0,0]) < 0.2:
                                    continue
                                # draw merged on both pages
                                for pp, oset in ((p,[h]), (p+1,[b])):
                                    bbx = (oset[0].get('bbox') or [0,0,0,0])
                                    payload = {
                                        "logical_table_key": f"hn::{hn}",
                                        "pages_in_group": [p + 1, p + 2],
                                    }
                                    ltk = payload.get("logical_table_key")
                                    source_ids = [f"logical_table_key:{ltk}"] if ltk else []
                                    _add(
                                        pp,
                                        bbx,
                                        "table_merged",
                                        payload,
                                        source_stage="07_reflow_section",
                                        source_ids=source_ids,
                                    )
                                    drew += 1
                                merged_groups = max(merged_groups, 1)
            except Exception:
                pass
        if drew == 0 and merged_groups == 0:
            logger.warning("09a: no table overlays drawn (check reflow/table JSON and block ids)")
        _append_timing(logs_dir, {"stage": "09a_pdf_annotator", "event": "draw_tables", "latency_ms": int((time.monotonic()-t_s)*1000)})

    # Tabs (sections + merged tables)
    # Figures
    if draw_figures:
        t_s = time.monotonic()
        figs_drawn = 0
        for f in figures:
            pg = _coerce_page(f.get("page"), f.get("page_idx"))
            bb = _safe_get_bbox(f)
            if bb is not None and pg is not None:
                fid = f.get("figure_id")
                desc = fig_desc.get(str(fid), "")
                title = f.get("title") or ""
                payload = {"figure_id": fid, "ai_description": desc, "title": title}
                if f.get("image_path"):
                    payload["image_ref"] = f.get("image_path")
                fid = payload.get("figure_id")
                source_ids = [f"figure_id:{fid}"] if fid is not None else []
                _add(
                    pg,
                    bb,
                    "figure",
                    payload,
                    source_stage="06_figure_extractor",
                    source_ids=source_ids,
                )
                figs_drawn += 1
            else:
                logger.warning(f"09a: skipping figure overlay (page/bbox invalid) fid={f.get('figure_id')} page={f.get('page')}")
        if figs_drawn == 0 and isinstance(figures, list) and len(figures) > 0:
            logger.warning("09a: figures were present but none were drawn — investigate page indices and bboxes")
        _append_timing(logs_dir, {"stage": "09a_pdf_annotator", "event": "draw_figures", "latency_ms": int((time.monotonic()-t_s)*1000)})

    # Knowledge chunks from Stage 07 reflowed sections
    if draw_text_chunks and reflowed_sections and block_lookup:
        t_s = time.monotonic()
        _text_budget: Dict[int, int] = {}
        for sec in reflowed_sections:
            blocks = (sec.get("reflowed_json", {}).get("blocks") or [])
            for idx, blk in enumerate(blocks):
                try:
                    src = blk.get("source") or {}
                    bids = src.get("block_ids") or []
                    if not bids:
                        continue
                    btype = str((blk.get("type") or "").lower())
                    if btype == "paragraph":
                        kind = "reflow_paragraph"; pref = "PAR"
                    elif btype == "list":
                        kind = "reflow_list"; pref = "LST"
                    elif btype == "heading":
                        kind = "reflow_heading"; pref = "HDG"
                    elif btype == "table":
                        kind = "reflow_table"; pref = "TBLB"
                    elif btype == "figure":
                        kind = "reflow_figure"; pref = "FIGB"
                    else:
                        kind = "text_chunk"; pref = "TXT"
                    per_page: dict[int, list[list[float]]] = {}
                    for bid in bids:
                        t = block_lookup.get(str(bid))
                        if not t:
                            continue
                        pg, bb = t
                        per_page.setdefault(pg, []).append(bb)
                    for pg, bbs in per_page.items():
                        if kind in ("reflow_paragraph", "reflow_list", "text_chunk"):
                            _text_budget.setdefault(pg, max_text_overlays_per_page)
                            if _text_budget[pg] <= 0:
                                continue
                            _text_budget[pg] -= 1
                        x0 = min(bb[0] for bb in bbs)
                        y0 = min(bb[1] for bb in bbs)
                        x1 = max(bb[2] for bb in bbs)
                        y1 = max(bb[3] for bb in bbs)
                        source_ids = [f"block_id:{bid}" for bid in bids]
                        _add(
                            pg,
                            [x0, y0, x1, y1],
                            kind,
                            {
                                "block_ids_count": len(bbs),
                                "reading_index": idx,
                                "block_kind": btype or blk.get("kind"),
                            },
                            source_stage="07_reflow_section",
                            source_ids=source_ids,
                            label_text=f"{pref} {idx}",
                        )
                except Exception:
                    continue
        _append_timing(logs_dir, {"stage": "09a_pdf_annotator", "event": "draw_text_chunks", "latency_ms": int((time.monotonic()-t_s)*1000)})

    # Requirements overlays
    if requirements:
        t_s = time.monotonic()
        req_drawn = 0
        sections_by_id = {str(s.get("id")): s for s in sections if s.get("id") is not None}
        for r in requirements:
            try:
                anchor = r.get("anchor") or {}
                pg = anchor.get("page")
                bb = anchor.get("bbox")
                src = r.get("source") or {}
                if (pg is None or not bb) and isinstance(src, dict):
                    pg = src.get("page_num", pg)
                    bb = src.get("bbox", bb)
                sec_id = r.get("section_id") or src.get("section_id")
                if pg is None or not bb:
                    if sec_id:
                        m = sections_by_id.get(str(sec_id))
                        if m:
                            pg = _coerce_page(m.get("page_start"), m.get("page_idx"), m.get("page"))
                            bb = _safe_get_bbox(m)
                if pg is None or not bb:
                    continue
                pg_int = _coerce_page(pg)
                if pg_int is None:
                    continue
                is_cond = bool(r.get("is_conditional")) or ("conditional" in str(r.get("category", "")).lower()) or bool(r.get("condition"))
                payload = {
                    "requirement_id": r.get("id"),
                    "title": r.get("title"),
                    "conditional": bool(is_cond),
                }
                source_ids = []
                rid = payload.get("requirement_id")
                if rid is not None:
                    source_ids.append(f"requirement_id:{rid}")
                if sec_id:
                    source_ids.append(f"section_id:{sec_id}")
                _add(
                    pg_int,
                    bb,
                    "requirement",
                    payload,
                    source_stage="07_requirements_miner",
                    source_ids=source_ids,
                )
                req_drawn += 1
            except Exception:
                continue
        if req_drawn == 0 and isinstance(requirements, list) and len(requirements) > 0:
            logger.warning("09a: requirements present but none were drawn — check anchors/section fallbacks")
        _append_timing(logs_dir, {"stage": "09a_pdf_annotator", "event": "draw_requirements", "latency_ms": int((time.monotonic()-t_s)*1000)})

    # Fallback merged-table detection using Stage 05 when reflow lacks linkage
    if prefer_reflow_tables and draw_tables and reflowed_sections and merged_groups == 0:
        try:
            # Identify header on page 0 from 05 tables
            t05 = json.loads(Path(tables_json).read_text(encoding="utf-8")) if isinstance(tables_json, (str, Path)) and Path(tables_json).exists() else {"tables": []}
            tabs05 = t05.get("tables", [])
            page0_tabs = [t for t in tabs05 if _coerce_page(t.get("page_index"), t.get("page_idx"), t.get("page")) == 0]
            if page0_tabs:
                hdr0 = None
                try:
                    df = page0_tabs[0].get("pandas_df_raw") or page0_tabs[0].get("pandas_df")
                    if isinstance(df, list) and df:
                        row0 = df[0]
                        if isinstance(row0, dict):
                            hdr0 = list(row0.keys())
                        elif isinstance(row0, list):
                            hdr0 = row0
                except Exception:
                    hdr0 = None
                # Find a best match on page 1 with same column count
                if isinstance(hdr0, list) and hdr0:
                    c0 = len(hdr0)
                    page1_tabs = [t for t in tabs05 if _coerce_page(t.get("page_index"), t.get("page_idx"), t.get("page")) == 1]
                    match = None
                    for t in page1_tabs:
                        try:
                            df = t.get("pandas_df_raw") or t.get("pandas_df")
                            if isinstance(df, list) and df:
                                r0 = df[0]
                                cols = list(r0.keys()) if isinstance(r0, dict) else (r0 if isinstance(r0, list) else [])
                                if len(cols) == c0:
                                    match = t; break
                        except Exception:
                            continue
                    if match:
                        # Draw merged boxes on both pages
                        for t in (page0_tabs[0], match):
                            pg = _coerce_page(t.get("page_index"), t.get("page_idx"), t.get("page"))
                            bb = _safe_get_bbox(t)
                            if bb is not None and pg is not None:
                                payload = {"logical_table_key": "p0p1_header_match"}
                                _add(
                                    pg,
                                    bb,
                                    "table_merged",
                                    payload,
                                    source_stage="05_table_extractor",
                                    source_ids=["logical_table_key:p0p1_header_match"],
                                )
                                merged_groups = 1
        except Exception:
            pass

    tabs_summary = {"mode": "none"}
    try:
        tabs = _collect_tabs(sections, overlays)
        logger.debug(f"09a tabs collected kinds: {[tab.get('kind') for tab in tabs]}")
        for tab in tabs:
            for pg in tab.get("pages", []):
                pages_touched.add(int(pg))
        tabs_summary = _draw_vertical_tabs(doc, tabs)
        logger.debug(f"09a tabs summary: {tabs_summary}")
    except Exception as e:
        logger.warning(f"Failed to draw tabs gutter: {e}")
        tabs_summary = {"mode": "error", "error": str(e)}

    # Stage 03 overlays
    if draw_headers03 and headers03:
        t_s = time.monotonic()
        for b in headers03:
            try:
                if not (b.get("suspicious_header") or b.get("is_suspicious")):
                    continue
                pg = _coerce_page(b.get("page_idx"), b.get("page"))
                bb = _safe_get_bbox(b)
                verdict = b.get("verdict") or ("accept" if b.get("suspicious_header") else "reject")
                lbl = f"HDR {verdict}"
                if bb and pg is not None:
                    bid = b.get("block_id")
                    payload = {"block_id": bid, "verdict": verdict}
                    source_ids = [f"block_id:{bid}"] if bid else []
                    _add(
                        pg,
                        bb,
                        "header_candidate",
                        payload,
                        source_stage="03_suspicious_headers",
                        source_ids=source_ids,
                        label_text=lbl,
                    )
            except Exception:
                continue
        _append_timing(logs_dir, {"stage": "09a_pdf_annotator", "event": "draw_headers03", "latency_ms": int((time.monotonic()-t_s)*1000)})

    # Stage 06b columns
    if draw_columns06b and layout06b and isinstance(layout06b, dict):
        t_s = time.monotonic()
        try:
            any_section = next(iter((layout06b.get("sections") or {}).values()), None)
            if isinstance(any_section, dict):
                grid_n = int(any_section.get("grid") or 0)
                cols = any_section.get("columns") or []
                if grid_n and cols:
                    for pidx in range(len(doc)):
                        page = doc[pidx]
                        r = page.rect
                        for c in cols:
                            try:
                                gx0 = int(c.get("x0", 0)); gx1 = int(c.get("x1", 0))
                                x0 = r.x0 + (r.width) * (gx0 / grid_n)
                                x1 = r.x0 + (r.width) * (gx1 / grid_n)
                                band = fitz.Rect(min(x0, x1), r.y0, max(x0, x1), r.y1)
                                try:
                                    if pdf_annotations:
                                        annot = page.add_rect_annot(band)
                                        annot.set_colors(stroke=_color_for_kind("columns"))
                                        try:
                                            annot.set_opacity(0.2)
                                        except Exception:
                                            pass
                                        annot.update()
                                    else:
                                        page.draw_rect(band, color=_color_for_kind("columns"), width=0.2, fill=None, overlay=True)
                                except Exception:
                                    page.draw_rect(band, color=_color_for_kind("columns"), width=0.2, fill=None, overlay=True)
                                if labels:
                                    page.insert_text(
                                        (band.x0 + 2, band.y0 + max(6, int(label_font_size))),
                                        f"COL {c.get('id')}",
                                        fontsize=max(5, int(label_font_size)),
                                        color=_color_for_kind("columns"),
                                    )
                                pages_touched.add(pidx)
                            except Exception:
                                continue
        except Exception:
            pass
        _append_timing(logs_dir, {"stage": "09a_pdf_annotator", "event": "draw_columns06b", "latency_ms": int((time.monotonic()-t_s)*1000)})

    # Stage 05 demoted (table -> text) markers
    try:
        t05 = json.loads(Path(tables_json).read_text(encoding="utf-8")) if isinstance(tables_json, (str, Path)) and Path(tables_json).exists() else {}
    except Exception:
        t05 = {}
    demoted_blocks = (t05.get("demoted_text_blocks") or []) if isinstance(t05, dict) else []
    if demoted_blocks:
        t_s = time.monotonic()
        for b in demoted_blocks:
            try:
                pg = int(b.get("page_idx") if b.get("page_idx") is not None else -1)
                bb = _safe_get_bbox(b)
                reason = (b.get("reason") or "demoted").upper()
                if bb is not None and pg >= 0:
                    payload = {"reason": b.get("reason"), "text": (b.get("text") or "")[:80]}
                    source_ids = []
                    if b.get("block_id") is not None:
                        source_ids.append(f"block_id:{b.get('block_id')}")
                    _add(
                        pg,
                        bb,
                        "table_rejected",
                        payload,
                        source_stage="05_table_extractor",
                        source_ids=source_ids,
                    )
            except Exception:
                continue
        _append_timing(logs_dir, {"stage": "09a_pdf_annotator", "event": "draw_demoted05", "latency_ms": int((time.monotonic()-t_s)*1000)})

    # Optional grid
    if draw_grid and isinstance(grid, int) and grid and grid > 1:
        t_s = time.monotonic()
        try:
            for pidx in range(len(doc)):
                page = doc[pidx]
                r = page.rect
                step_x = (r.x1 - r.x0) / float(grid)
                step_y = (r.y1 - r.y0) / float(grid)
                color = _color_for_kind("grid")
                for i in range(1, grid):
                    x = r.x0 + step_x * i
                    page.draw_line(fitz.Point(x, r.y0), fitz.Point(x, r.y1), color=color, width=0.3)
                    y = r.y0 + step_y * i
                    page.draw_line(fitz.Point(r.x0, y), fitz.Point(r.x1, y), color=color, width=0.3)
                pages_touched.add(pidx)
        except Exception:
            pass
        _append_timing(logs_dir, {"stage": "09a_pdf_annotator", "event": "draw_grid", "latency_ms": int((time.monotonic()-t_s)*1000)})

    # Final gutter pass: draw plaques last so they sit above lanes/overlays
    try:
        logger.info("Final gutter pass")
        for _pg, items in sorted(pending_left_tags.items()):
            if not items:
                continue
            lane = lane_left_by_page.get(_pg)
            if not lane:
                continue
            try:
                page = doc[_pg]
            except Exception:
                continue
            for it in items:
                try:
                    rect = it.get("rect")
                    label = str(it.get("label") or "").strip()
                    if not rect or not label:
                        continue
                    _draw_gutter_tag(
                        page,
                        lane,
                        rect,
                        label,
                        color=(it.get("color") or (0.12, 0.12, 0.12)),
                        font=float(it.get("font", 9.0)),
                    )
                except Exception:
                    continue
        for _pg, caps in sorted(pending_right_tags.items()):
            if not caps:
                continue
            lane = lane_right_by_page.get(_pg) or lane_left_by_page.get(_pg)
            if not lane:
                continue
            try:
                page = doc[_pg]
            except Exception:
                continue
            for (y0, y1) in caps:
                try:
                    _draw_t_endcaps(page, lane, y0, y1)
                except Exception:
                    continue
    except Exception as e:
        logger.warning(f"Gutter final pass failed: {e}")

    # Save outputs (annotated PDF first)
    annotated_pdf = stage_dir / "annotated.pdf"
    try:
        doc.save(str(annotated_pdf))
        logger.info(f"Annotated PDF saved: {annotated_pdf}")
    finally:
        doc.close()

    # Per-page previews (only pages touched)
    if render_previews:
        t_s = time.monotonic()
        try:
            src = fitz.open(str(annotated_pdf))
            try:
                for pidx in sorted(pages_touched):
                    try:
                        page = src[pidx]
                        scale = PREVIEW_DPI / 72.0
                        mat = fitz.Matrix(scale, scale)
                        pix = page.get_pixmap(matrix=mat, alpha=False)
                        out_png = vis_dir / f"page_{pidx+1:04d}.png"
                        pix.save(str(out_png))
                    except Exception:
                        continue
            finally:
                src.close()
        except Exception as e:
            logger.warning(f"Failed to render previews: {e}")
        _append_timing(logs_dir, {"stage": "09a_pdf_annotator", "event": "render_previews", "latency_ms": int((time.monotonic()-t_s)*1000)})

    # Overlay map bundle for web viewer
    try:
        _emit_overlay_map(stage_dir, overlays, pages_touched, PREVIEW_DPI)
    except Exception as e:
        logger.warning(f"Failed to emit overlay_map.json: {e}")

    # Write overlay JSON with summary
    try:
        by_kind: Dict[str, int] = {}
        for o in overlays:
            k = str(o.get("kind") or "")
            by_kind[k] = by_kind.get(k, 0) + 1
        # Best-effort merged-table groups count (from label payload)
        merged_groups = 0
        try:
            merged_groups = len({o.get("logical_table_key") for o in overlays if o.get("kind") == "table_merged" and o.get("logical_table_key")})
        except Exception:
            merged_groups = 0
        header = {
            "summary": {
                "total_overlays": len(overlays),
                "by_kind": by_kind,
                "pages_touched": sorted(int(p)+1 for p in pages_touched),
                "merged_table_groups": merged_groups,
                "tabs": tabs_summary,
            },
            "source": {
                "pdf_path": str(pdf_path),
                "sections_json": str(sections_json),
                "tables_json": str(tables_json),
                "figures_json": str(figures_json),
                "reflowed_json": str(reflowed_json) if reflowed_json else None,
                "blocks02_json": str(blocks02_json) if blocks02_json else None,
                "headers03_json": str(headers03_json) if headers03_json else None,
                "layout06b_json": str(layout06b_json) if layout06b_json else None,
            },
            "overlays": overlays,
        }
        (json_dir / "annotations.json").write_text(json.dumps(header, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to write annotations.json: {e}")

    # Legend JSON for colors
    try:
        legend = {
            "colors": {k: list(v) for k, v in COLORS.items()},
            "labels": "SEC/TBL/FIG/TXT/PAR/LST/HDG/REQ prefixes map to section/table/figure/text/paragraph/list/heading/requirement respectively. Section spans in left gutter show T (start) and ⊥ (end).",
        }
        (json_dir / "legend.json").write_text(json.dumps(legend, indent=2))
    except Exception:
        pass

    # Optional: color-aware header overlay directly onto the source PDF
    if rewrite_headers:
        def _parse_hex_color(h: str | None) -> tuple[float, float, float]:
            try:
                if not h:
                    return (0, 0, 0)
                hs = h.lstrip('#')
                return (int(hs[0:2],16)/255.0, int(hs[2:4],16)/255.0, int(hs[4:6],16)/255.0)
            except Exception:
                return (0, 0, 0)

        try:
            src_doc = fitz.open(str(pdf_path))
            with src_doc:
                for s in sections:
                    try:
                        blocks = s.get("blocks") or []
                        if not blocks:
                            continue
                        hdr = blocks[0]
                        pg = hdr.get("page") if hdr.get("page") is not None else hdr.get("page_idx")
                        bb = _safe_get_bbox(hdr) or _safe_get_bbox(s)
                        title = s.get("title") or ""
                        color_hex = ((s.get("metadata") or {}).get("header_color_hex") or None)
                        color = _parse_hex_color(color_hex)
                        fsf = (hdr.get("first_span_font") or {}) if isinstance(hdr, dict) else {}
                        size = float(fsf.get("size", 0) or 0) or 11.0
                        fname = str(fsf.get("name") or "").lower()
                        if "times" in fname:
                            fontname = "times"
                        elif "helvetica" in fname or "arial" in fname or "sans" in fname:
                            fontname = "helv"
                        elif "courier" in fname or "mono" in fname:
                            fontname = "cour"
                        else:
                            fontname = "helv"
                        if pg is None or bb is None or not title:
                            continue
                        page = src_doc[int(pg)]
                        rect = fitz.Rect(float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])) & page.rect
                        if replace_text_layer:
                            try:
                                page.add_redact_annot(rect, fill=None)
                                page.apply_redactions()
                            except Exception as _e:
                                logger.debug(f"redaction failed on p{pg} rect={rect}: {_e}")
                        page.insert_textbox(rect, title, fontsize=size, color=color, fontname=fontname, align=0)
                    except Exception:
                        continue
                target_path = pdf_path if overwrite_pdf else pdf_path.with_name(pdf_path.stem + "__headers_patched.pdf")
                try:
                    src_doc.save(str(target_path), incremental=True, deflate=True)
                except Exception:
                    tmp = target_path.with_suffix(target_path.suffix + ".tmp")
                    src_doc.save(str(tmp))
                    if overwrite_pdf:
                        try:
                            tmp.replace(target_path)
                        except Exception:
                            fallback = pdf_path.with_name(pdf_path.stem + "__headers_patched.pdf")
                            tmp.replace(fallback)
                            target_path = fallback
                    else:
                        pass
                logger.info(f"Section headers overlaid in: {target_path}")
        except Exception as e:
            logger.warning(f"Header rewrite failed (continuing): {e}")

    # Artifacts index and timings
    _write_artifacts_index(stage_dir)
    try:
        _append_timing(logs_dir, {"stage": "09a_pdf_annotator", "event": "total", "latency_ms": int((time.time()-t0)*1000)})
        _summarize_timings(logs_dir)
    except Exception:
        pass

    if sink_id is not None:
        try:
            logger.remove(sink_id)
        except Exception:
            pass

    return annotated_pdf


if __name__ == "__main__":
    import sys
    argv = sys.argv[1:]
    if argv and argv[0] == "sanity":
        sys.exit(sanity())
    print("Usage: python -m extractor.pipeline.steps.09a_pdf_annotator sanity")
