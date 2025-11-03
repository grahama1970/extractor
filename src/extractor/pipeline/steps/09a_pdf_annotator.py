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
from pathlib import Path
from typing import Any, Dict

from loguru import logger
import fitz  # PyMuPDF

# No CLI framework; import and call run(...)

# Color map for overlay kinds (RGB in 0..1)
COLORS: Dict[str, tuple[float, float, float]] = {
    "section": (0.0, 0.627, 0.0),           # green
    "section_frame": (0.0, 0.627, 0.0),
    "header_candidate": (1.0, 0.0, 1.0),    # magenta
    "columns": (0.0, 1.0, 1.0),             # cyan
    "table": (0.898, 0.224, 0.207),         # red-ish
    "table_merged": (0.6, 0.0, 0.0),        # darker red for logical merged tables
    "figure": (0.117, 0.533, 0.902),        # blue-ish
    "text_chunk": (1.0, 0.5, 0.0),          # orange
    "reflow_paragraph": (0.984, 0.549, 0.0),
    "reflow_list": (1.0, 0.761, 0.0),
    "reflow_heading": (0.557, 0.141, 0.667),
    "reflow_table": (0.777, 0.157, 0.157),
    "reflow_figure": (0.223, 0.286, 0.671),
    "requirement": (1.0, 0.843, 0.0),       # gold
    "grid": (0.7, 0.7, 0.7),                # gray
    "table_rejected": (0.35, 0.35, 0.35),   # dark gray for demoted not-table
}


def _safe_get_bbox(obj: dict[str, Any]) -> list[float] | None:
    bb = obj.get("bbox") or obj.get("box")
    if not isinstance(bb, (list, tuple)) or len(bb) != 4:
        return None
    try:
        return [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])]
    except Exception:
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
    label_font_size: int = 6,
    stroke_width: float = 1.0,
    pdf_annotations: bool = True,
    render_previews: bool = True,
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
    overlays: list[dict[str, Any]] = []
    overlay_id = 0
    pages_touched: set[int] = set()

    def _normalized_page_index(idx: int) -> int | None:
        try:
            _pg = int(idx)
        except Exception:
            return None
        if _pg >= len(doc) and _pg - 1 >= 0 and _pg - 1 < len(doc):
            _pg = _pg - 1
        if _pg < 0 or _pg >= len(doc):
            return None
        return _pg

    def _color_for_kind(kind: str) -> tuple[float, float, float]:
        return COLORS.get(kind, (0.3, 0.3, 0.3))

    def _add(page_idx: int, bbox: list[float] | None, kind: str, payload: dict[str, Any], *, label_text: str | None = None) -> None:
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
        rect = fitz.Rect(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)) & page.rect
        # Avoid zero-area: expand minimally when degenerate
        if rect.width <= 0.1 or rect.height <= 0.1:
            rect = fitz.Rect(rect.x0, rect.y0, rect.x0 + max(1.0, rect.width), rect.y0 + max(1.0, rect.height)) & page.rect
        color = _color_for_kind(kind)
        drew = False
        if pdf_annotations:
            try:
                annot = page.add_rect_annot(rect)
                annot.set_colors(stroke=color)
                try:
                    annot.set_border(width=max(0.5, float(stroke_width)))
                except Exception:
                    pass
                try:
                    annot.set_opacity(0.35)
                except Exception:
                    pass
                try:
                    info = {}
                    if label_text:
                        info["title"] = str(label_text)[:120]
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
                page.draw_rect(rect, color=color, width=max(0.5, float(stroke_width)), fill=None, overlay=True)
            except Exception:
                pass
            if labels:
                try:
                    txt = label_text or payload.get("title") or payload.get("figure_id") or payload.get("table_index")
                    if txt:
                        page.insert_text(
                            (rect.x0 + 2, rect.y0 + max(6, int(label_font_size))),
                            str(txt)[:120],
                            fontsize=max(5, int(label_font_size)),
                            color=color,
                        )
                except Exception:
                    pass
        overlays.append({"overlay_id": overlay_id, "page": _pg, "bbox": [rect.x0, rect.y0, rect.x1, rect.y1], "kind": kind, **payload})
        overlay_id += 1
        pages_touched.add(_pg)

    # Sections (prefer reflowed sections when available)
    if draw_sections:
        t_s = time.monotonic()
        drew = 0
        if prefer_reflow_sections and reflowed_sections and block_lookup:
            for s in reflowed_sections:
                try:
                    sid = s.get("id") or s.get("section_id") or s.get("sectionId")
                    blocks = (s.get("reflowed_json", {}) or {}).get("blocks", [])
                    per_page: dict[int, list[list[float]]] = {}
                    for blk in blocks:
                        bids = ((blk.get("source") or {}).get("block_ids") or [])
                        for bid in bids:
                            t = block_lookup.get(str(bid))
                            if not t:
                                continue
                            pg, bb = t
                            per_page.setdefault(pg, []).append(bb)
                    for pg, bbs in per_page.items():
                        x0 = min(bb[0] for bb in bbs); y0 = min(bb[1] for bb in bbs)
                        x1 = max(bb[2] for bb in bbs); y1 = max(bb[3] for bb in bbs)
                        _add(pg, [x0, y0, x1, y1], "section", {"id": sid, "title": s.get("title")}, label_text=f"SEC {sid}: {s.get('title')}")
                        drew += 1
                except Exception:
                    continue
        if drew == 0:
            # Fallback to raw sections
            for s in sections:
                pg0 = int(s.get("page_start") or s.get("page_idx") or -1)
                bb = _safe_get_bbox(s)
                if bb is not None and pg0 >= 0:
                    _add(pg0, bb, "section", {"id": s.get("id"), "title": s.get("title")}, label_text=f"SEC {s.get('id')}: {s.get('title')}")
                    drew += 1
        if drew == 0:
            logger.warning("09a: no section overlays drawn (check reflow/sections JSON and block ids)")
        _append_timing(logs_dir, {"stage": "09a_pdf_annotator", "event": "draw_sections", "latency_ms": int((time.monotonic()-t_s)*1000)})

    # Tables (prefer logical merged tables from reflow when available)
    if draw_tables:
        t_s = time.monotonic()
        drew = 0
        merged_groups = 0
        if prefer_reflow_tables and reflowed_sections and block_lookup:
            # Group by logical_table_id (preferred) or header_norm/title fallback
            groups: dict[str, list[dict[str, Any]]] = {}
            for s in reflowed_sections:
                for blk in ((s.get("reflowed_json", {}) or {}).get("blocks", []) or []):
                    if (blk.get("type") or blk.get("kind")) != "table":
                        continue
                    lid = blk.get("logical_table_id")
                    hdr = (blk.get("header_norm") or blk.get("title") or "").strip().lower()
                    key = str(lid or hdr or blk.get("id") or blk.get("table_id") or f"sec{ s.get('id') }")
                    groups.setdefault(key, []).append(blk)
            for gkey, blist in groups.items():
                per_page: dict[int, list[list[float]]] = {}
                page_set: set[int] = set()
                for blk in blist:
                    bids = ((blk.get("source") or {}).get("block_ids") or [])
                    for bid in bids:
                        t = block_lookup.get(str(bid))
                        if not t:
                            continue
                        pg, bb = t
                        per_page.setdefault(pg, []).append(bb)
                        page_set.add(pg)
                kind = "table_merged" if len(page_set) > 1 else "table"
                if kind == "table_merged":
                    merged_groups += 1
                for pg, bbs in per_page.items():
                    try:
                        x0 = min(bb[0] for bb in bbs); y0 = min(bb[1] for bb in bbs)
                        x1 = max(bb[2] for bb in bbs); y1 = max(bb[3] for bb in bbs)
                        _add(pg, [x0, y0, x1, y1], kind, {"logical_table_key": gkey, "pages_in_group": sorted(int(p)+1 for p in page_set)}, label_text=f"TBL {'M' if kind=='table_merged' else ''} {gkey}")
                        drew += 1
                    except Exception:
                        continue
        if drew == 0:
            # Fallback to raw tables
            for t in tables:
                pg = int(t.get("page_index") or t.get("page_idx") or -1)
                bb = _safe_get_bbox(t)
                if bb is not None and pg >= 0:
                    headers_preview = None
                    try:
                        hdrs = t.get("headers")
                        if not hdrs:
                            df = t.get("pandas_df_raw") or t.get("pandas_df")
                            if isinstance(df, list) and df:
                                row0 = df[0]
                                if isinstance(row0, dict):
                                    hdrs = list(row0.keys())
                                elif isinstance(row0, list):
                                    hdrs = row0
                        if isinstance(hdrs, list) and hdrs:
                            headers_preview = " | ".join(str(h).strip() for h in hdrs[:6])
                    except Exception:
                        headers_preview = None
                    _add(
                        pg,
                        bb,
                        "table",
                        {"table_index": t.get("table_index"), "headers_preview": headers_preview},
                        label_text=f"TBL {t.get('table_index')} :: {headers_preview or ''}",
                    )
                    drew += 1
        if drew == 0:
            logger.warning("09a: no table overlays drawn (check reflow/table JSON and block ids)")
        _append_timing(logs_dir, {"stage": "09a_pdf_annotator", "event": "draw_tables", "latency_ms": int((time.monotonic()-t_s)*1000)})

    # Figures
    if draw_figures:
        t_s = time.monotonic()
        figs_drawn = 0
        for f in figures:
            pg = int(f.get("page") or f.get("page_idx") or -1)
            bb = _safe_get_bbox(f)
            if bb is not None and pg >= 0:
                fid = f.get("figure_id")
                desc = fig_desc.get(str(fid), "")
                title = f.get("title") or ""
                payload = {"figure_id": fid, "ai_description": desc, "title": title}
                if f.get("image_path"):
                    payload["image_ref"] = f.get("image_path")
                # Include title or first words of description in the label for readability
                label = f"FIG {fid}"
                if isinstance(title, str) and title.strip():
                    label += f": {title[:60]}"
                elif isinstance(desc, str) and desc.strip():
                    label += f": {desc[:60]}"
                _add(pg, bb, "figure", payload, label_text=label)
                figs_drawn += 1
            else:
                logger.warning(f"09a: skipping figure overlay (page/bbox invalid) fid={f.get('figure_id')} page={f.get('page')}")
        if figs_drawn == 0 and isinstance(figures, list) and len(figures) > 0:
            logger.warning("09a: figures were present but none were drawn — investigate page indices and bboxes")
        _append_timing(logs_dir, {"stage": "09a_pdf_annotator", "event": "draw_figures", "latency_ms": int((time.monotonic()-t_s)*1000)})

    # Knowledge chunks from Stage 07 reflowed sections
    if draw_text_chunks and reflowed_sections and block_lookup:
        t_s = time.monotonic()
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
                        x0 = min(bb[0] for bb in bbs)
                        y0 = min(bb[1] for bb in bbs)
                        x1 = max(bb[2] for bb in bbs)
                        y1 = max(bb[3] for bb in bbs)
                        _add(
                            pg,
                            [x0, y0, x1, y1],
                            kind,
                            {
                                "block_ids_count": len(bbs),
                                "reading_index": idx,
                                "block_kind": btype or blk.get("kind"),
                            },
                            label_text=f"{pref} {idx}",
                        )
                except Exception:
                    continue
        _append_timing(logs_dir, {"stage": "09a_pdf_annotator", "event": "draw_text_chunks", "latency_ms": int((time.monotonic()-t_s)*1000)})

    # Requirements overlays
    if requirements:
        t_s = time.monotonic()
        req_drawn = 0
        for r in requirements:
            try:
                anchor = r.get("anchor") or {}
                pg = anchor.get("page")
                bb = anchor.get("bbox")
                if pg is None or not bb:
                    sec_id = r.get("section_id")
                    if sec_id:
                        m = next((s for s in sections if str(s.get("id")) == str(sec_id)), None)
                        if m:
                            pg = int(m.get("page_start") or m.get("page_idx") or -1)
                            bb = _safe_get_bbox(m)
                if pg is None or not bb:
                    continue
                label = (r.get("id") or r.get("title") or "REQ")
                is_cond = bool(r.get("is_conditional")) or ("conditional" in str(r.get("category", "")).lower()) or bool(r.get("condition"))
                kind = "requirement"
                if is_cond:
                    label = f"COND {label}"
                _add(int(pg), bb, kind, {"requirement_id": r.get("id"), "title": r.get("title"), "conditional": bool(is_cond)}, label_text=f"REQ {label}")
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
            page0_tabs = [t for t in tabs05 if int(t.get("page_index") or t.get("page_idx") or -1) == 0]
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
                    page1_tabs = [t for t in tabs05 if int(t.get("page_index") or t.get("page_idx") or -1) == 1]
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
                            pg = int(t.get("page_index") or t.get("page_idx") or -1)
                            bb = _safe_get_bbox(t)
                            if bb is not None and pg >= 0:
                                _add(pg, bb, "table_merged", {"logical_table_key": "p0p1_header_match"}, label_text="TBL M header-match")
                                merged_groups = 1
        except Exception:
            pass

    # Stage 03 overlays
    if draw_headers03 and headers03:
        t_s = time.monotonic()
        for b in headers03:
            try:
                if not (b.get("suspicious_header") or b.get("is_suspicious")):
                    continue
                pg = int(b.get("page_idx") if b.get("page_idx") is not None else b.get("page") or -1)
                bb = _safe_get_bbox(b)
                verdict = b.get("verdict") or ("accept" if b.get("suspicious_header") else "reject")
                lbl = f"HDR {verdict}"
                if (bb and pg >= 0):
                    _add(pg, bb, "header_candidate", {"block_id": b.get("block_id"), "verdict": verdict}, label_text=lbl)
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
                    _add(pg, bb, "table_rejected", {"reason": b.get("reason"), "text": (b.get("text") or "")[:80]}, label_text=f"TBL REJ: {reason}")
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
                        zoom = 1200.0 / max(1.0, float(page.rect.width))
                        mat = fitz.Matrix(zoom, zoom)
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
            "labels": "SEC/TBL/FIG/TXT/PAR/LST/HDG/REQ prefixes map to section/table/figure/text/paragraph/list/heading/requirement respectively.",
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
    print("Import and call run(...); no CLI framework required.")
