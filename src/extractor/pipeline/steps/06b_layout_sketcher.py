#!/usr/bin/env python3
"""
06b Layout Sketcher (skeleton)

Goal: build a deterministic, text-only layout sketch for each section so Stage 07
can be text-first and avoid images. This file is a minimal stub to let reviewers
propose concrete diffs. It should:
- Read Stage 04/05/06 artifacts from the results dir
- Produce 06b_layout_sketch.json with {sections: {id: {grid,elements,quick_summary}}}
- Be deterministic (no LLM/vision). Only bbox math + sorting.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import asyncio
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger
from extractor.pipeline.utils.step_sanity import run_step_sanity
from extractor.pipeline.steps.scillm_preflight_validator import require_scillm_preflight
from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.layout.sketcher import (
    _build_section_sketch,
    _build_section_sketch_llm,
    run,
)
EMIT_MERGE_HINTS = os.getenv("STAGE06B_EMIT_MERGE_HINTS", "0").lower() in ("1", "true", "yes", "y")


GRID = 12  # default grid granularity (rows = cols = GRID)
SCHEMA_VERSION = "0.2.0"
STEP_NAME = "06b_layout_sketcher"


def sanity() -> int:
    return run_step_sanity(STEP_NAME)
# Env toggles
# Default VLM-assisted sketch OFF for determinism; enable explicitly when desired
ALLOW_VLM = os.getenv("STAGE06B_ALLOW_VLM", "0").lower() in ("1", "true", "yes", "y")
PYMUPDF_FALLBACK = os.getenv("STAGE06B_PYMUPDF_FALLBACK", "").lower() in ("1", "true", "yes", "y")
SOURCE_PDF_ENV = os.getenv("STAGE06B_SOURCE_PDF", "").strip() or None
EMIT_MERGE_HINTS = os.getenv("STAGE06B_EMIT_MERGE_HINTS", "").lower() in ("1", "true", "yes", "y")
# Safety switch: enable/disable header→body propagation without reverting code.
# Default ON (insurance only; turn OFF by exporting STAGE06B_HEADER_PROPAGATION=0)
HEADER_PROPAGATION = os.getenv("STAGE06B_HEADER_PROPAGATION", "1").lower() in ("1", "true", "yes", "y")
VISUAL_PROOF = os.getenv("STAGE06B_VISUAL_PROOF", "").lower() in ("1", "true", "yes", "y")


def _norm(v: float, a: float, b: float) -> float:
    if b <= a:
        return 0.0
    x = (v - a) / (b - a)
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


def _grid_bbox(bbox: list[float], page: list[float], grid: int) -> dict[str, int]:
    """Map page bbox → grid cells using half-open contract [x0,x1), [y0,y1).

    - floor for starts, ceil for ends
    - clamp to [0, grid]
    - ensure non-degenerate (at least 1x1 cell)
    """
    import math

    x0, y0, x1, y1 = bbox or [0.0, 0.0, 0.0, 0.0]
    px0, py0, px1, py1 = page or [0.0, 0.0, 1.0, 1.0]

    nx0 = _norm(float(x0), float(px0), float(px1))
    ny0 = _norm(float(y0), float(py0), float(py1))
    nx1 = _norm(float(x1), float(px0), float(px1))
    ny1 = _norm(float(y1), float(py0), float(py1))

    gx0 = max(0, min(grid, int(math.floor(nx0 * grid))))
    gy0 = max(0, min(grid, int(math.floor(ny0 * grid))))
    gx1 = max(0, min(grid, int(math.ceil(nx1 * grid))))
    gy1 = max(0, min(grid, int(math.ceil(ny1 * grid))))

    if gx1 <= gx0:
        gx1 = min(grid, gx0 + 1)
    if gy1 <= gy0:
        gy1 = min(grid, gy0 + 1)

    return {"x0": gx0, "y0": gy0, "x1": gx1, "y1": gy1}


def _summ(text: str, limit: int = 80) -> str:
    if not text:
        return ""
    s = " ".join(str(text).split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _norm_text(s: str) -> str:
    return " ".join((s or "").split())


def _text_sha1(s: str) -> str:
    import hashlib

    return hashlib.sha1(_norm_text(s).encode("utf-8")).hexdigest()


def _area(b: list[float]) -> float:
    if not b or len(b) != 4:
        return 0.0
    return max(0.0, (b[2] - b[0])) * max(0.0, (b[3] - b[1]))


def _aspect(b: list[float]) -> float:
    w = max(1e-6, (b[2] - b[0]))
    h = max(1e-6, (b[3] - b[1]))
    return w / h


def _detect_columns(
    elements: list[dict[str, Any]],
    page_bbox: list[float],
    min_gap_ratio: float = 0.04,
) -> list[list[float]]:
    """Detect 1–3 columns deterministically using x-center gaps.

    Returns list of [x0,x1] in page coordinates.
    """
    pts: list[float] = []
    for e in elements:
        b = e.get("bbox")
        if not b or len(b) != 4:
            continue
        pts.append((float(b[0]) + float(b[2])) / 2.0)
    pts.sort()
    if len(pts) < 3:
        return [[page_bbox[0], page_bbox[2]]]
    gaps: list[tuple[float, int]] = []
    for i in range(len(pts) - 1):
        gaps.append((pts[i + 1] - pts[i], i))
    page_w = max(1e-6, (page_bbox[2] - page_bbox[0]))
    cuts = [i for g, i in gaps if g / page_w >= min_gap_ratio]
    if not cuts:
        return [[page_bbox[0], page_bbox[2]]]
    bounds: list[float] = [page_bbox[0]] + [
        (pts[i] + pts[i + 1]) / 2.0 for i in cuts
    ] + [page_bbox[2]]
    cols = [[bounds[j], bounds[j + 1]] for j in range(len(bounds) - 1)]
    # Cap at 3 columns to avoid fragmentation on noisy inputs
    return cols[:3]


def _assign_cols_and_span(
    bbox: List[float],
    columns: List[List[float]],
) -> Tuple[List[int], bool]:
    """Return ([col_ids], spans_columns) based on overlap with column bands."""
    x0, _, x1, _ = [float(v) for v in (bbox or [0, 0, 0, 0])]
    col_ids: List[int] = []
    spans = False
    if not columns:
        return [0], False
    w = max(1e-6, x1 - x0)
    for i, (cx0, cx1) in enumerate(columns):
        ov = max(0.0, min(x1, float(cx1)) - max(x0, float(cx0)))
        if ov / w >= 0.5:
            col_ids.append(i)
    if len(col_ids) >= 2:
        spans = True
    if not col_ids:
        # fallback to single best overlap
        best = max(
            range(len(columns)),
            key=lambda i: max(0.0, min(x1, float(columns[i][1])) - max(x0, float(columns[i][0]))),
        )
        col_ids = [best]
    return col_ids, spans


def _col_id_for(xc: float, columns: list[list[float]]) -> int:
    for i, (a, b) in enumerate(columns):
        if a <= xc <= b:
            return i
    return 0


def _iou(a: list[float], b: list[float]) -> float:
    try:
        ax0, ay0, ax1, ay1 = map(float, a)
        bx0, by0, bx1, by1 = map(float, b)
        ix0 = max(ax0, bx0)
        iy0 = max(ay0, by0)
        ix1 = min(ax1, bx1)
        iy1 = min(ay1, by1)
        iw = max(0.0, ix1 - ix0)
        ih = max(0.0, iy1 - iy0)
        inter = iw * ih
        if inter <= 0:
            return 0.0
        area_a = max(0.0, (ax1 - ax0) * (ay1 - ay0))
        area_b = max(0.0, (bx1 - bx0) * (by1 - by0))
        union = max(1e-9, area_a + area_b - inter)
        return inter / union
    except Exception as exc:
        log_stage_error(STEP_NAME, exc, {'context': '06b'})
        raise
def _build_flow_stream(
    elements: list[dict[str, Any]],
    columns_grid: list[dict[str, int]],
    *,
    exclude_header_footer: bool,
    place_floats: str = "inline",
) -> str:
    # Deterministic linearization with explicit dividers for LLM prompts
    lines: list[str] = []
    lines.append("[SECTION START]")
    col_count = len(columns_grid) if columns_grid else 1
    lines.append(f"[COLUMNS {col_count}]")

    # Group by column_id
    by_col: dict[int, list[dict[str, Any]]] = {}
    for e in elements:
        if exclude_header_footer and e.get("header_footer_candidate"):
            continue
        by_col.setdefault(int(e.get("column_id", 0)), []).append(e)

    def _emit_elem(e: dict[str, Any]) -> str:
        gid = e.get("id") or "?"
        if e.get("kind") == "text":
            return f"[PARA id={gid}] {e.get('summary','')}"
        if e.get("kind") == "table":
            hdr = e.get("summary", "").replace("\n", " ")
            return f"[TABLE id={gid} header=\"{hdr}\"]"
        if e.get("kind") == "figure":
            cap = e.get("summary", "").replace("\n", " ")
            anch = e.get("anchor_element_id")
            dist = e.get("anchor_distance")
            tail = f" [ANCHOR={anch} dist={dist}]" if anch else ""
            return f"[FIGURE id={gid} cap=\"{cap}\"]{tail}"
        return f"[ELEM id={gid} kind={e.get('kind')}]"

    # Place floats policy
    if place_floats not in {"inline", "sidebar", "append"}:
        place_floats = "inline"

    for cidx in sorted(by_col):
        lines.append(f"[COL {cidx} START]")
        col_elems = by_col[cidx]
        if place_floats == "inline":
            # Emit in reading_order; floats appear where they sort
            for e in col_elems:
                lines.append(_emit_elem(e))
        elif place_floats == "sidebar":
            # Emit non-floats first, then floats
            for e in col_elems:
                if e.get("kind") == "text":
                    lines.append(_emit_elem(e))
            for e in col_elems:
                if e.get("kind") in ("table", "figure"):
                    lines.append(_emit_elem(e))
        else:  # append
            for e in col_elems:
                if e.get("kind") != "figure" and e.get("kind") != "table":
                    lines.append(_emit_elem(e))
            for e in col_elems:
                if e.get("kind") in ("table", "figure"):
                    lines.append(_emit_elem(e))
        lines.append(f"[COL {cidx} END]")
    lines.append("[SECTION END]")
    return "\n".join(lines)


def _collect_page_index_from_sections(
    sections: List[dict],
) -> Dict[int, Dict[str, Any]]:
    """
    Build a per-page index with text bboxes and a coarse page bbox from Stage 04 sections.
    """
    page_index: Dict[int, Dict[str, Any]] = {}
    for sec in sections or []:
        for b in sec.get("blocks") or []:
            page = int(b.get("page") or b.get("page_idx") or b.get("page_index") or -1)
            bbox = b.get("bbox") or []
            if page < 0 or len(bbox) != 4:
                continue
            rec = page_index.setdefault(page, {"text_bboxes": [], "page_bbox": [None, None, None, None]})
            rec["text_bboxes"].append([float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])])
            # expand page bbox as union of observed text boxes
            pb = rec["page_bbox"]
            x0, y0, x1, y1 = [float(x) for x in bbox]
            pb[0] = x0 if pb[0] is None else min(pb[0], x0)
            pb[1] = y0 if pb[1] is None else min(pb[1], y0)
            pb[2] = x1 if pb[2] is None else max(pb[2], x1)
            pb[3] = y1 if pb[3] is None else max(pb[3], y1)
    # normalize page_bbox defaults
    for _, rec in page_index.items():
        pb = rec.get("page_bbox") or [None, None, None, None]
        if any(v is None for v in pb):
            rec["page_bbox"] = [0.0, 0.0, 1.0, 1.0]
    return page_index


def _pymupdf_fill_missing_pages(page_index: Dict[int, Dict[str, Any]], source_pdf: Optional[Path]) -> None:
    """Optional: fill missing text_bboxes using PyMuPDF on pages with no text boxes."""
    if not PYMUPDF_FALLBACK or source_pdf is None or not source_pdf.exists():
        return
    try:
        import fitz  # PyMuPDF
    except Exception as exc:
        log_stage_error(STEP_NAME, exc, {'context': '06b'})
        raise
    try:
        doc = fitz.open(str(source_pdf))
        for pno in range(len(doc)):
            rec = page_index.setdefault(
                pno,
                {"text_bboxes": [], "page_bbox": [0.0, 0.0, doc[pno].rect.width, doc[pno].rect.height]},
            )
            if rec.get("text_bboxes"):
                continue
            blocks = doc[pno].get_text("blocks")
            for blk in blocks:
                if not isinstance(blk, (list, tuple)) or len(blk) < 5:
                    continue
                x0, y0, x1, y1 = [float(blk[0]), float(blk[1]), float(blk[2]), float(blk[3])]
                txt = (blk[4] or "").strip()
                if txt:
                    rec["text_bboxes"].append([x0, y0, x1, y1])
            # ensure page_bbox set
            if not rec.get("page_bbox"):
                r = doc[pno].rect
                rec["page_bbox"] = [0.0, 0.0, float(r.width), float(r.height)]
        doc.close()
    except Exception as exc:
        log_stage_error(STEP_NAME, exc, {'context': '06b'})
        raise
def _build_page_layout(
    page_index: Dict[int, Dict[str, Any]],
    *,
    min_gap_ratio: float,
    grid: int,
) -> Dict[int, Dict[str, Any]]:
    """
    Compute columns per page once, re-used by all sections.
    """
    layout: Dict[int, Dict[str, Any]] = {}
    for pno, rec in page_index.items():
        page_bbox: List[float] = rec.get("page_bbox") or [0.0, 0.0, 1.0, 1.0]
        # Build synthetic elements view from text bboxes for column detection
        elements = [{"bbox": b} for b in rec.get("text_bboxes") or []]
        cols = _detect_columns(elements, page_bbox, min_gap_ratio=min_gap_ratio)
        # express columns in grid units for convenient downstream overlays
        grid_cols: list[dict[str, int]] = []
        for idx, (cx0, cx1) in enumerate(cols):
            gb = _grid_bbox([cx0, page_bbox[1], cx1, page_bbox[3]], page_bbox, grid)
            grid_cols.append({"id": idx, "x0": gb["x0"], "x1": gb["x1"]})
        # naive confidence (multi-column → higher)
        conf = 0.6 if len(cols) <= 1 else 0.85
        layout[pno] = {
            "page_bbox": page_bbox,
            "columns": cols,
            "grid_columns": grid_cols,
            "conf": {"columns": conf, "source": "marker"},
        }
    return layout


def main(
    results_dir: Path = Path("data/results/pipeline"),
    grid: int = GRID,
    summary_limit: int = 80,
    flow_text: bool = False,
    min_gap_ratio: float = 0.04,
    header_footer_band: float = 0.05,
    place_floats: str = "inline",
) -> None:
    # Run and, if generated deterministically, re-map grid/summary settings by rebuilding per-section
    run(str(results_dir), str(results_dir), min_gap_ratio=min_gap_ratio)
    # If caller requested non-default grid or summary_limit, rebuild deterministic sections in-memory and write file back
    if True:  # Always rebuild deterministically with requested knobs for predictability
        base = Path(results_dir)
        sec_json = base / "04_section_builder" / "json_output" / "04_sections.json"
        if sec_json.exists():
            data = json.loads(sec_json.read_text(encoding="utf-8"))
            sections = data.get("sections") or []
            # Precompute page layout for the rebuild pass as well
            page_index = _collect_page_index_from_sections(sections)
            # Try to pick a source PDF from 04 payload or env for fallback
            source_pdf = None
            try:
                top_source = data.get("source_pdf") or None
                if top_source and isinstance(top_source, str):
                    p = Path(top_source)
                    source_pdf = p if p.exists() else None
            except Exception as exc:
                log_stage_error(STEP_NAME, exc, {'context': '06b'})
                raise
            if SOURCE_PDF_ENV and not source_pdf:
                p = Path(SOURCE_PDF_ENV)
                source_pdf = p if p.exists() else None
            _pymupdf_fill_missing_pages(page_index, source_pdf)
            page_layout = _build_page_layout(page_index, min_gap_ratio=min_gap_ratio, grid=grid)
            # Load tables/figures for rebuild pass
            tabs_by_sec: Dict[str, List[dict]] = {}
            figs_by_sec: Dict[str, List[dict]] = {}
            try:
                tpath = base / "05_table_extractor" / "json_output" / "05_tables.json"
                if tpath.exists():
                    tdata = json.loads(tpath.read_text(encoding="utf-8")).get("tables") or []
                    for t in tdata:
                        sid = str(t.get("section_id") or "")
                        if sid:
                            tabs_by_sec.setdefault(sid, []).append(t)
            except Exception as exc:
                log_stage_error(STEP_NAME, exc, {'context': '06b'})
                raise
            try:
                fpath = base / "06_figure_extractor" / "json_output" / "06_figures.json"
                if fpath.exists():
                    fdata = json.loads(fpath.read_text(encoding="utf-8")).get("figures") or []
                    for f in fdata:
                        sid = str(f.get("section_id") or "")
                        if sid:
                            figs_by_sec.setdefault(sid, []).append(f)
            except Exception as exc:
                log_stage_error(STEP_NAME, exc, {'context': '06b'})
                raise
            rebuilt: dict[str, Any] = {"sections": {}}
            for sec in sections:
                sid = str(sec.get("id"))
                sketch = _build_section_sketch(
                    sec,
                    grid,
                    summary_limit=summary_limit,
                    min_gap_ratio=min_gap_ratio,
                    header_footer_band=header_footer_band,
                    place_floats=place_floats,
                    include_flow=True,
                    page_layout=page_layout,
                    tables_for_section=tabs_by_sec.get(sid, []),
                    figures_for_section=figs_by_sec.get(sid, []),
                    emit_merge_hints=EMIT_MERGE_HINTS,
                    base_results_dir=base,
                    source_pdf=source_pdf,
                )
                rebuilt["sections"][sid] = sketch
                if flow_text and isinstance(sketch.get("flow_stream"), str):
                    txt_dir = base / "06b_layout_sketcher" / "text_output"
                    txt_dir.mkdir(parents=True, exist_ok=True)
                    (txt_dir / f"flow_{sid}.txt").write_text(sketch["flow_stream"], encoding="utf-8")
            out_dir = base / "06b_layout_sketcher" / "json_output"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "06b_layout_sketch.json").write_text(
                json.dumps(rebuilt, ensure_ascii=False, indent=2)
            )
    # Schema validation + timings + router close + sink teardown
    t_ms = int((_t.monotonic() - _t0) * 1000)
    latest_path = base / "06b_layout_sketcher" / "json_output" / "06b_layout_sketch.json"
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    if not isinstance(latest, dict) or not isinstance(latest.get("sections"), dict):
        raise ValueError("invalid 06b_layout_sketch.json schema: expected {sections:{...}}")
    logger.info(f"06b_layout_sketcher: sections={len(latest.get('sections',{}))}")
    with ((base / "06b_layout_sketcher") / "timings.jsonl").open("a", encoding="utf-8") as fp:
        fp.write(json.dumps({"stage":"06b_layout_sketcher","latency_ms":t_ms,"outcome":"ok"}) + "\n")
    ((base / "06b_layout_sketcher") / "timings_summary.json").write_text(json.dumps({"total_ms":t_ms}, indent=2))
    # Remove sink
    if locals().get("sink_id") is not None:
        logger.remove(locals().get("sink_id"))
if __name__ == "__main__":
    import sys
    argv = sys.argv[1:]
    if argv and argv[0] == "sanity":
        sys.exit(sanity())
    print("Usage: python -m extractor.pipeline.steps.06b_layout_sketcher sanity")
