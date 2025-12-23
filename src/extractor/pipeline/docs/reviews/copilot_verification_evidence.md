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
from extractor.pipeline.utils.reliability import log_stage_error
import fitz  # PyMuPDF
from extractor.pipeline.utils.step_sanity import run_step_sanity
# Import from new utils/visuals package (extracted functions)
from extractor.pipeline.utils.visuals import (
    COLORS as _COLORS,
    HUMAN_KIND as _HUMAN_KIND,
    TAB_COLORS as _TAB_COLORS,
    lighten as _lighten,
    style_for_kind as _style_for_kind,
    color_for_kind as _color_for_kind,
    safe_get_bbox as _safe_get_bbox,
    rect_from_pdf_bbox as _rect_from_pdf_bbox,
    rect_for_kind as _rect_for_kind,
    wrap_label_lines as _wrap_label_lines,
    format_label as _format_label,
    stable_overlay_id as _stable_overlay_id,
    headers_preview_from_table as _headers_preview_from_table,
    rows_preview_from_table as _rows_preview_from_table,
    table_payload_from_obj as _table_payload_from_obj,
)

# No CLI framework; import and call run(...)

STEP_NAME = "09a_pdf_annotator"


def sanity() -> int:
    return run_step_sanity(STEP_NAME)



# Toggle: draw figure caption callout box on the page (off to avoid duplicate description;
# description is surfaced in the data pane instead).
DRAW_FIGURE_CAPTION_BOX = False

# Aliases for imported constants (backward compatibility)
COLORS = _COLORS
HUMAN_KIND = _HUMAN_KIND
TAB_COLORS = _TAB_COLORS

# Local-only constants (not in utils/visuals)
GUTTER_SIDE = "left"
GUTTER_WIDTH = 0.0
GUTTER_PAD = 0.0
PLAQUE_PAD_X = 0.0
PLAQUE_PAD_Y = 0.0
GUTTER_FILL = None
GUTTER_BORDER = None
PLAQUE_FILL = None
PLAQUE_BORDER = None
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


def _draw_page_gutter_side(page: fitz.Page, side: str = "left") -> fitz.Rect:
    """Return the gutter rect on the requested side (no fill/stroke)."""
    return fitz.Rect()

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
        except Exception as exc:
            log_stage_error('09a_pdf_annotator', exc, {'context': '09a'})
            raise
            pass
        try:
            annot.set_colors(stroke=PLAQUE_BORDER)
        except Exception as exc:
            log_stage_error('09a_pdf_annotator', exc, {'context': '09a'})
            raise
            pass
        try:
            annot.set_opacity(0.98)
        except Exception as exc:
            log_stage_error('09a_pdf_annotator', exc, {'context': '09a'})
            raise
            pass
        annot.update()
    except Exception as exc:
        log_stage_error('09a_pdf_annotator', exc, {'context': '09a'})
        raise
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
    except Exception as exc:
        log_stage_error('09a_pdf_annotator', exc, {'context': '09a'})
        raise
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
    except Exception as exc:
        log_stage_error('09a_pdf_annotator', exc, {'context': '09a'})
        raise
        page.draw_line(fitz.Point(x, y0), fitz.Point(x, y1), color=color, width=1.0)
        page.draw_line(fitz.Point(x - 6, y0), fitz.Point(x + 6, y0), color=color, width=1.0)
        page.draw_line(fitz.Point(x - 6, y1), fitz.Point(x + 6, y1), color=color, width=1.0)


def _draw_section_title_plaque(page: fitz.Page, rect: fitz.Rect, text: str, stroke=(0.86, 0.25, 0.2), font=11.0) -> None:
    if not text:
        return
    t = text.strip()
    max_w = min(rect.width * 0.9, 360.0)
    while page.get_text_length(t, fontsize=font) > max_w and len(t) > 5:
