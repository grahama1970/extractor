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
    drawing as draw,
    layout,
)
from extractor.pipeline.utils.visuals.geometry import coerce_page as _coerce_page
from extractor.pipeline.utils.visuals.runner import run

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
# GUTTER_*, PLAQUE_*, LABEL_*, TAB_* constants removed (moved to layout/drawing)
PREVIEW_DPI = 144
# PREVIEW_DPI kept for local usage
# MAX_TABS, TAB_* removed (moved to layout)


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
    except Exception as exc:
        log_stage_error('09a_pdf_annotator', exc, {'context': '09a'})
        raise
        pass


def _append_timing(logs_dir: Path, record: Dict[str, Any]) -> None:
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        with (logs_dir / "timings.jsonl").open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record) + "\n")
    except Exception as exc:
        log_stage_error('09a_pdf_annotator', exc, {'context': '09a'})
        raise


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
            except Exception as exc:
                log_stage_error('09a_pdf_annotator', exc, {'context': '09a'})
                continue  # Skip malformed line, don't crash
        lat.sort()
        def _pct(p: float) -> float:
            if not lat:
                return 0.0
            idx = int(max(0, min(len(lat) - 1, round(p * (len(lat) - 1)))))
            return float(lat[idx])
        summary = {"events": count, "p50_ms": _pct(0.50), "p95_ms": _pct(0.95)}
        (logs_dir / "timings_summary.json").write_text(json.dumps(summary, indent=2))
    except Exception as exc:
        log_stage_error('09a_pdf_annotator', exc, {'context': '09a'})
        raise


