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


GRID = 12  # default grid granularity (rows = cols = GRID)
SCHEMA_VERSION = "0.2.0"
# Env toggles
ALLOW_VLM = os.getenv("STAGE06B_ALLOW_VLM", "").lower() in ("1", "true", "yes", "y")
PYMUPDF_FALLBACK = os.getenv("STAGE06B_PYMUPDF_FALLBACK", "").lower() in ("1", "true", "yes", "y")
SOURCE_PDF_ENV = os.getenv("STAGE06B_SOURCE_PDF", "").strip() or None
EMIT_MERGE_HINTS = os.getenv("STAGE06B_EMIT_MERGE_HINTS", "").lower() in ("1", "true", "yes", "y")
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
    except Exception:
        return 0.0


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
    except Exception:
        return
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
    except Exception:
        pass


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


def _build_section_sketch(
    sec: dict[str, Any],
    grid: int,
    *,
    summary_limit: int = 80,
    min_gap_ratio: float = 0.04,
    header_footer_band: float = 0.05,
    place_floats: str = "inline",
    include_flow: bool = True,
    page_layout: Optional[Dict[int, Dict[str, Any]]] = None,
    tables_for_section: Optional[List[dict]] = None,
    figures_for_section: Optional[List[dict]] = None,
    emit_merge_hints: bool = EMIT_MERGE_HINTS,
) -> dict[str, Any]:
    if page_layout is None:
        page_layout = {}
    first_page_idx = int(sec.get("page_start", sec.get("page_index", 0)) or 0)
    page_bbox = (page_layout.get(first_page_idx, {}) or {}).get("page_bbox") or sec.get("bbox") or sec.get("page_bbox") or [0, 0, 1, 1]
    section_page_idx = int(sec.get("page_index", first_page_idx))

    raw_elements: list[dict[str, Any]] = []
    # Text blocks
    for b in sec.get("blocks") or []:
        bbox = b.get("bbox") or [0, 0, 0, 0]
        text = (b.get("text") or "")
        raw_elements.append(
            {
                "kind": "text",
                "id": b.get("id") or b.get("block_id"),
                "bbox": bbox,
                "grid_bbox": _grid_bbox(bbox, page_bbox, grid),
                "summary": _summ(text, summary_limit),
                "text_sha1": _text_sha1(text),
                "page": int(b.get("page") or b.get("page_idx") or b.get("page_index") or section_page_idx),
                "area": _area(bbox),
                "aspect": _aspect(bbox),
                "char_count": len(text or ""),
                "role": b.get("role") or "para",
            }
        )
    # Tables from Stage 05 (associated via section_id)
    for t in (tables_for_section or []):
        bbox = t.get("bbox") or [0, 0, 0, 0]
        hdr = t.get("header") or t.get("columns") or (t.get("pandas_metrics") or {}).get("columns") or []
        hdr_text = " | ".join([str(h) for h in hdr])
        raw_elements.append(
            {
                "kind": "table",
                "id": t.get("id") or t.get("table_id") or f"tbl_{t.get('table_index')}",
                "bbox": bbox,
                "grid_bbox": _grid_bbox(bbox, page_bbox, grid),
                "summary": _summ(hdr_text, summary_limit),
                "page": int(t.get("page") or t.get("page_idx") or t.get("page_index") or section_page_idx),
                "area": _area(bbox),
                "aspect": _aspect(bbox),
                "confidence": float((t.get("confidence") or (t.get("pandas_metrics") or {}).get("data_density") or 1.0)),
                "llm_assist": bool((t.get("llm_assist") or {}).get("patch")),
            }
        )
    # Figures from Stage 06
    for f in (figures_for_section or []):
        bbox = f.get("bbox") or [0, 0, 0, 0]
        cap = f.get("caption") or f.get("ai_description") or ""
        raw_elements.append(
            {
                "kind": "figure",
                "id": f.get("figure_id") or f.get("id"),
                "bbox": bbox,
                "grid_bbox": _grid_bbox(bbox, page_bbox, grid),
                "summary": _summ(cap, summary_limit),
                "page": int(f.get("page") or f.get("page_idx") or f.get("page_index") or section_page_idx),
                "area": _area(bbox),
                "aspect": _aspect(bbox),
                "llm_assist": bool((f.get("ai_description") or "").strip()),
            }
        )

    # Determine columns by page (use cache where possible)
    columns_by_page: Dict[int, List[List[float]]] = {}
    for e in raw_elements:
        p = int(e.get("page", section_page_idx))
        if p in page_layout:
            columns_by_page[p] = page_layout[p]["columns"]
        else:
            sub_elems = [x for x in raw_elements if int(x.get("page", section_page_idx)) == p]
            columns_by_page[p] = _detect_columns(sub_elems, page_bbox, min_gap_ratio=min_gap_ratio)

    # Assign reading order deterministically (col → top → left → -area → id)
    enriched: list[dict[str, Any]] = []
    for e in raw_elements:
        b = e.get("bbox") or [0, 0, 0, 0]
        p = int(e.get("page", section_page_idx))
        cols = columns_by_page.get(p) or [[page_bbox[0], page_bbox[2]]]
        col_ids, spans = _assign_cols_and_span(b, cols)
        e["column_id"] = col_ids[0] if col_ids else 0
        e["col_ids"] = col_ids
        e["spans_columns"] = spans
        e["_top"] = float(b[1])
        e["_left"] = float(b[0])
        e["_neg_area"] = -float(e.get("area", _area(b)))
        # Header/footer candidates: near top/bottom bands
        try:
            height = (page_bbox[3] - page_bbox[1]) or 1.0
            top_band = page_bbox[1] + height * header_footer_band
            bot_band = page_bbox[3] - height * header_footer_band
            y0 = float(b[1])
            y1 = float(b[3])
            e["header_footer_candidate"] = bool(y1 <= top_band or y0 >= bot_band)
        except Exception:
            e["header_footer_candidate"] = False
        enriched.append(e)
    enriched.sort(key=lambda x: (
        int(x.get("column_id", 0)),
        round(float(x.get("_top", 0.0)), 3),
        round(float(x.get("_left", 0.0)), 3),
        round(float(x.get("_neg_area", 0.0)), 1),
        str(x.get("id", "")),
    ))
    for i, e in enumerate(enriched):
        e["reading_order"] = i
        e.pop("_top", None)
        e.pop("_left", None)
        e.pop("_neg_area", None)

    # Overlap flag via pairwise IoU
    try:
        for i, a in enumerate(enriched):
            a_bbox = a.get("bbox") or [0, 0, 0, 0]
            overlapped = False
            for j, b in enumerate(enriched):
                if i == j:
                    continue
                if _iou(a_bbox, b.get("bbox") or [0, 0, 0, 0]) > 0.01:
                    overlapped = True
                    break
            a["overlapped"] = overlapped
    except Exception:
        pass

    # Anchor floats (figures/tables) to nearest text
    texts = [e for e in enriched if e.get("kind") == "text"]
    for f in enriched:
        if f.get("kind") not in ("figure", "table"):
            continue
        fb = f.get("bbox") or [0, 0, 0, 0]
        fx = (fb[0] + fb[2]) / 2.0
        fy = (fb[1] + fb[3]) / 2.0
        best = None
        for t in texts:
            tb = t.get("bbox") or [0, 0, 0, 0]
            tx = (tb[0] + tb[2]) / 2.0
            ty = (tb[1] + tb[3]) / 2.0
            d = abs(ty - fy) * 1.5 + abs(tx - fx)
            if best is None or d < best[0]:
                best = (d, t.get("id"))
        if best:
            f["anchor_element_id"] = best[1]
            f["anchor_distance"] = float(round(best[0], 3))

    # quick summary: prefer the topmost text (heading-ish), fallback to first table
    top_text = next((e for e in enriched if e.get("kind") == "text" and e.get("summary")), None)
    first_table = next((e for e in enriched if e.get("kind") == "table" and e.get("summary")), None)
    qs = " | ".join(
        [s for s in [top_text.get("summary", "") if top_text else "", first_table.get("summary", "") if first_table else ""] if s]
    )

    # Columns expressed in grid units for downstream uniformity (use first page of section)
    pages_present = sorted({int(e.get("page", section_page_idx)) for e in enriched})
    first_p = pages_present[0] if pages_present else section_page_idx
    grid_cols: list[dict[str, int]] = []
    for idx, (cx0, cx1) in enumerate(columns_by_page.get(first_p, [[page_bbox[0], page_bbox[2]]])):
        gb = _grid_bbox([cx0, page_bbox[1], cx1, page_bbox[3]], page_bbox, grid)
        grid_cols.append({"id": idx, "x0": gb["x0"], "x1": gb["x1"]})

    # Stats and contract
    pages_present = sorted({int(e.get("page", section_page_idx)) for e in enriched})
    # Section ordering confidence: mean of per-page column confidence where available
    try:
        conf_vals = [float((page_layout.get(p, {}).get("conf") or {}).get("columns", 0.0)) for p in pages_present]
        ordering_conf = float(sum(conf_vals) / max(1, len(conf_vals))) if conf_vals else 0.6
    except Exception:
        ordering_conf = 0.6

    # Optional: table merge hints (non-binding)
    table_merge_hints: List[Dict[str, Any]] = []
    if emit_merge_hints and tables_for_section and len(tables_for_section) > 1:
        def _rows_cols(t: Dict[str, Any]) -> Tuple[int, int]:
            m = t.get("pandas_metrics") or {}
            shp = m.get("shape") or [0, 0]
            try:
                return int(shp[0] or 0), int(shp[1] or 0)
            except Exception:
                return 0, 0
        def _h_iou(a: List[float], b: List[float]) -> float:
            try:
                ax0, _, ax1, _ = a
                bx0, _, bx1, _ = b
                inter = max(0.0, min(float(ax1), float(bx1)) - max(float(ax0), float(bx0)))
                uni = max(float(ax1), float(bx1)) - min(float(ax0), float(bx0))
                return float(inter / uni) if uni > 0 else 0.0
            except Exception:
                return 0.0
        tabs = sorted(list(tables_for_section), key=lambda t: (int(t.get("page_index", 0) or 0), int(t.get("table_index", 0) or 0)))
        for i in range(len(tabs) - 1):
            t1, t2 = tabs[i], tabs[i + 1]
            r1, c1 = _rows_cols(t1)
            r2, c2 = _rows_cols(t2)
            if c1 <= 0 or c1 != c2:
                continue
            if int(t2.get("page_index", 0) or 0) > int(t1.get("page_index", 0) or 0) + 1:
                continue
            iou = _h_iou(t1.get("bbox", []) or [0, 0, 0, 0], t2.get("bbox", []) or [0, 0, 0, 0])
            if iou < 0.2:
                continue
            header_body = (r1 == 1 and r2 >= 2)
            density1 = float((t1.get("pandas_metrics") or {}).get("data_density") or 0.0)
            density2 = float((t2.get("pandas_metrics") or {}).get("data_density") or 0.0)
            conf = 0.5 + 0.3 * iou + 0.1 * (1.0 if header_body else 0.0) + 0.1 * (1.0 if abs(density1 - density2) <= 0.2 else 0.0)
            table_merge_hints.append({
                "group_id": f"G_tbl_{t1.get('table_index')}_{t2.get('table_index')}",
                "tables": [t1.get("id") or f"tbl_{t1.get('table_index')}", t2.get("id") or f"tbl_{t2.get('table_index')}"],
                "reason": ["same_columns", "adjacent_pages_or_same", f"h_iou>={iou:.2f}"] + (["header_body"] if header_body else []),
                "scores": {"h_iou": round(iou, 2), "density_compat": round(1.0 - abs(density1 - density2), 2)},
                "header_body": header_body,
                "conf": round(min(0.95, conf), 2),
            })
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "grid": grid,
        "grid_contract": {"cell": "half-open", "rounding": "floor/ceil", "eps": 1e-6},
        "columns": grid_cols,
        "elements": [
            {k: v for k, v in e.items() if k not in ("bbox",)} | {"grid_bbox": e["grid_bbox"]}
            for e in enriched
        ],
        # Keep original bboxes for audit
        "elements_original_bbox": [
            {"id": e.get("id"), "bbox": e.get("bbox")}
            for e in enriched
        ],
        "page_breaks": pages_present,
        "quick_summary": qs,
        "conf": {"ordering": ordering_conf},
    }
    if emit_merge_hints and table_merge_hints:
        result["table_merge_hints"] = table_merge_hints
    if include_flow:
        result["flow_stream"] = _build_flow_stream(result["elements"], grid_cols, exclude_header_footer=True, place_floats=place_floats)
    return result


def _build_section_sketch_llm(
    sec: dict[str, Any],
    base_results_dir: Path,
    *,
    grid: int = GRID,
    timeout: float = 30.0,
) -> dict[str, Any] | None:
    """Optional VLM-assisted layout sketch using scillm on the section visual.

    - Uses scillm.completion with explicit x-api-key (no Bearer) for Chutes.
    - Model: STAGE06B_VLM_MODEL or LITELLM_LARGE_VLLM_MODEL or LITELLM_VLM_MODEL.
    - Returns a dict with keys {grid,elements,quick_summary} or None on failure.
    """
    try:
        import json as _json
        import os

        from extractor.pipeline.utils.model_params import image_file_to_data_url

        base = os.getenv("CHUTES_API_BASE", "").strip()
        key = os.getenv("CHUTES_API_KEY", "").strip()
        if not (base and key):
            return None
        # Single-source VLM model only
        from extractor.pipeline.utils.model_select import get_vlm_model
        model = get_vlm_model()
        if not model:
            return None
        # Resolve visual path; require an image to attach
        vrel = sec.get("visual_path")
        if not vrel:
            return None
        vpath = (base_results_dir / vrel).resolve()
        if not vpath.exists():
            return None
        data_url = image_file_to_data_url(vpath)
        sys_prompt = (
            "You analyze a PDF section image and return a STRICT JSON layout sketch. "
            "No prose, no code fences. Grid is an integer (default 12). Elements is an array of objects: "
            "{kind: 'text'|'table'|'figure', grid_bbox:{x0:int,y0:int,x1:int,y1:int}, summary:string}."
        )
        user_text = (
            f"Return only this JSON: {{grid:int,elements:[{{kind:'text'|'table'|'figure',grid_bbox:{{x0:int,y0:int,x1:int,y1:int}},summary:string}}],quick_summary:string}}. "
            f"Use grid={grid}. Clamp grid_bbox to [0,{grid}]."
        )
        messages = [
            {"role": "system", "content": sys_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ]
        from scillm import acompletion as sc_acompletion
        resp = asyncio.run(sc_acompletion(
            model=model,
            custom_llm_provider="openai_like",
            api_base=base,
            api_key=None,
            extra_headers={"x-api-key": key},
            messages=messages,
            response_format={"type":"json_object"},
            temperature=0,
            timeout=timeout,
        ))
        content = (resp.get("choices") or [{}])[0].get("message", {}).get("content", "")
        if not isinstance(content, str) or not content.strip():
            return None
        out = _json.loads(content)
        if not isinstance(out, dict) or "elements" not in out:
            return None
        # Enrich LLM result with schema and contract to align with deterministic path
        if isinstance(out, dict):
            out.setdefault("schema_version", SCHEMA_VERSION)
            out.setdefault("grid_contract", {"cell": "half-open", "rounding": "floor/ceil", "eps": 1e-6})
        return out
    except Exception:
        return None


def run(input_path: str, output_path: str, **kwargs) -> dict[str, Any]:
    """
    Build 06b_layout_sketch.json under 06b_layout_sketcher/json_output/.
    - input_path: base results dir (unused; for symmetry)
    - output_path: base results dir containing 04/05/06 outputs
    """
    base = Path(output_path)
    # Try to find Stage 04 sections file
    sec_json = base / "04_section_builder" / "json_output" / "04_sections.json"
    if not sec_json.exists():
        # fall back to a generic path if present
        alt = base / "06_sections.json"
        if alt.exists():
            sec_json = alt
        else:
            # nothing to do
            out = {"sections": {}}
            out_dir = base / "06b_layout_sketcher" / "json_output"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "06b_layout_sketch.json").write_text(json.dumps(out, indent=2))
            return out

    data = json.loads(sec_json.read_text(encoding="utf-8"))
    sections = data.get("sections") or []
    # Try shared page-geometry cache first
    page_layout: Dict[int, Dict[str, Any]] = {}
    try:
        from extractor.pipeline.utils.page_geometry_cache import build_or_load as _pg_build
        src_pdf = None
        try:
            sp = data.get("source_pdf")
            src_pdf = Path(sp) if isinstance(sp, str) else None
        except Exception:
            src_pdf = None
        cache = _pg_build(base, sections, src_pdf)
        for pno, pg in cache.pages.items():
            page_bbox = [0.0, 0.0, float(pg.width or 1.0), float(pg.height or 1.0)]
            cols = _detect_columns([{"bbox": list(bb)} for bb in (pg.text_bboxes or [])], page_bbox, min_gap_ratio=kwargs.get("min_gap_ratio", 0.04) if isinstance(kwargs.get("min_gap_ratio", 0.04), (float, int)) else 0.04)
            grid_cols = []
            for idx, (cx0, cx1) in enumerate(cols):
                gb = _grid_bbox([cx0, page_bbox[1], cx1, page_bbox[3]], page_bbox, GRID)
                grid_cols.append({"id": idx, "x0": gb["x0"], "x1": gb["x1"]})
            conf = 0.6 if len(cols) <= 1 else 0.85
            page_layout[pno] = {
                "page_bbox": page_bbox,
                "columns": cols,
                "grid_columns": grid_cols,
                "conf": {"columns": conf, "source": "pg_cache"},
            }
    except Exception:
        page_layout = {}
    # Optionally load Stage 05/06 to attach tables/figures by section
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
    except Exception:
        pass
    try:
        fpath = base / "06_figure_extractor" / "json_output" / "06_figures.json"
        if fpath.exists():
            fdata = json.loads(fpath.read_text(encoding="utf-8")).get("figures") or []
            for f in fdata:
                sid = str(f.get("section_id") or "")
                if sid:
                    figs_by_sec.setdefault(sid, []).append(f)
    except Exception:
        pass
    if not page_layout:
        # Per-page layout cache from section blocks (+ optional PyMuPDF for missing)
        page_index = _collect_page_index_from_sections(sections)
        # Try to resolve a source PDF for fallback
        source_pdf: Optional[Path] = None
        try:
            top_source = data.get("source_pdf") or None
            if top_source and isinstance(top_source, str):
                p = Path(top_source)
                source_pdf = p if p.exists() else None
        except Exception:
            source_pdf = None
        if SOURCE_PDF_ENV and not source_pdf:
            p = Path(SOURCE_PDF_ENV)
            source_pdf = p if p.exists() else None
        _pymupdf_fill_missing_pages(page_index, source_pdf)
        page_layout = _build_page_layout(
            page_index,
            min_gap_ratio=kwargs.get("min_gap_ratio", 0.04) if isinstance(kwargs.get("min_gap_ratio", 0.04), (float, int)) else 0.04,
            grid=GRID,
        )

    sketches: dict[str, Any] = {"sections": {}}
    for sec in sections:
        sid = str(sec.get("id"))
        sketch = None
        # VLM path only if explicitly allowed
        if ALLOW_VLM:
            sketch = _build_section_sketch_llm(sec, base, grid=GRID)
        if not sketch:
            sketch = _build_section_sketch(
                sec,
                GRID,
                summary_limit=kwargs.get("summary_limit", 80) if isinstance(kwargs.get("summary_limit", 80), int) else 80,
                min_gap_ratio=kwargs.get("min_gap_ratio", 0.04) if isinstance(kwargs.get("min_gap_ratio", 0.04), (float, int)) else 0.04,
                header_footer_band=kwargs.get("header_footer_band", 0.05) if isinstance(kwargs.get("header_footer_band", 0.05), (float, int)) else 0.05,
                place_floats=kwargs.get("place_floats", "inline") if isinstance(kwargs.get("place_floats", "inline"), str) else "inline",
                include_flow=True,
                page_layout=page_layout,
                tables_for_section=tabs_by_sec.get(sid, []),
                figures_for_section=figs_by_sec.get(sid, []),
                emit_merge_hints=EMIT_MERGE_HINTS,
            )
        sketches["sections"][sid] = sketch

    # Optional: render column/order overlays per section (visual proof)
    try:
        if VISUAL_PROOF:
            from extractor.pipeline.visual.overlay import Box, draw_overlays
            # Resolve source PDF
            src_pdf = None
            try:
                tp = data.get("source_pdf")
                src_pdf = Path(tp) if isinstance(tp, str) and Path(tp).exists() else None
            except Exception:
                src_pdf = None
            if not src_pdf and SOURCE_PDF_ENV:
                p = Path(SOURCE_PDF_ENV)
                src_pdf = p if p.exists() else None
            if src_pdf:
                for sid, sk in sketches.get("sections", {}).items():
                    try:
                        elems = sk.get("elements") or []
                        orig = {e.get("id"): (e.get("bbox") or None) for e in sk.get("elements_original_bbox", [])}
                        boxes = []
                        for e in elems:
                            bid = e.get("id")
                            bb = orig.get(bid)
                            if not bb or len(bb) != 4:
                                continue
                            pg = int(e.get("page", 0) or 0)
                            kind = e.get("kind") or "elem"
                            ro = e.get("reading_order")
                            col = int(e.get("column_id", 0))
                            label = f"{kind}:{ro}@c{col}"
                            color = (0, 170, 255) if kind == "text" else ((0, 200, 0) if kind == "table" else (255, 128, 0))
                            boxes.append(Box(page=pg, x0=float(bb[0]), y0=float(bb[1]), x1=float(bb[2]), y1=float(bb[3]), label=label, color=color, width=3))
                        if boxes:
                            vout = base / "06b_layout_sketcher" / "visual_output" / sid
                            draw_overlays(src_pdf, boxes, vout)
                            # attach a relative path list for convenience
                            try:
                                imgs = [str(p.relative_to(base)) for p in vout.glob("*.png")]
                                if imgs:
                                    sk.setdefault("visual_overlays", imgs)
                            except Exception:
                                pass
                    except Exception:
                        continue
    except Exception:
        pass

    out_dir = base / "06b_layout_sketcher" / "json_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "06b_layout_sketch.json").write_text(json.dumps(sketches, ensure_ascii=False, indent=2))
    return sketches


## CLI removed: call run(...) or main(...) from Python.
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
            except Exception:
                source_pdf = None
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
            except Exception:
                pass
            try:
                fpath = base / "06_figure_extractor" / "json_output" / "06_figures.json"
                if fpath.exists():
                    fdata = json.loads(fpath.read_text(encoding="utf-8")).get("figures") or []
                    for f in fdata:
                        sid = str(f.get("section_id") or "")
                        if sid:
                            figs_by_sec.setdefault(sid, []).append(f)
            except Exception:
                pass
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


if __name__ == "__main__":
    print("Import and call run(...) or main(...); no CLI framework required.")
