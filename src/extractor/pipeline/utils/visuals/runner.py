"""
Stage 09a PDF annotation runner.

Extracted from 09a_pdf_annotator.py.
"""

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict

try:
    import fitz  # PyMuPDF (optional — regression testing only)
except ImportError:
    fitz = None  # type: ignore[assignment]
from loguru import logger

from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.visuals import (
    COLORS,
    HUMAN_KIND,
    coerce_page as _coerce_page,
    color_for_kind as _color_for_kind,
    format_label as _format_label,
    rect_for_kind as _rect_for_kind,
    safe_get_bbox as _safe_get_bbox,
    stable_overlay_id as _stable_overlay_id,
    style_for_kind as _style_for_kind,
    table_payload_from_obj as _table_payload_from_obj,
)
from extractor.pipeline.utils.visuals import drawing as draw
from extractor.pipeline.utils.visuals import layout
from extractor.pipeline.utils.visuals.colors import PREVIEW_DPI
from extractor.pipeline.utils.visuals.drawing import (
    draw_section_title_plaque as _draw_section_title_plaque,
    draw_t_endcaps as _draw_t_endcaps,
    draw_table_metrics as _draw_table_metrics,
    draw_table_preview_box as _draw_table_preview_box,
)


def _append_timing(logs_dir: Path, record: dict[str, Any]) -> None:
    """Append timing record to JSONL log file."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / "timings.jsonl"
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(record) + "\n")


def _summarize_timings(logs_dir: Path) -> None:
    """Summarize timing data from the timings.jsonl log file."""
    timings_path = logs_dir / "timings.jsonl"
    if not timings_path.exists():
        return
    calls = 0
    latency_sum = 0
    by_event: dict[str, int] = {}
    with timings_path.open("r", encoding="utf-8") as fp:
        for line in fp:
            if not line.strip():
                continue
            rec = json.loads(line)
            calls += 1
            latency = int(rec.get("latency_ms") or 0)
            latency_sum += latency
            event = str(rec.get("event") or "unknown")
            by_event[event] = by_event.get(event, 0) + latency
    summary = {
        "calls": calls,
        "latency_ms_total": latency_sum,
        "latency_ms_avg": (latency_sum // calls) if calls else 0,
        "by_event_latency_ms": by_event,
    }
    (logs_dir / "timings_summary.json").write_text(json.dumps(summary, indent=2))


def _write_artifacts_index(stage_dir: Path) -> None:
    """Write a JSON index of artifact file paths in the specified directory."""
    artifacts = []
    for path in stage_dir.rglob("*"):
        if path.is_file():
            artifacts.append(str(path.relative_to(stage_dir)))
    artifacts.sort()
    (stage_dir / "artifacts_index.json").write_text(
        json.dumps({"artifacts": artifacts}, indent=2)
    )


def sanity() -> int:
    """Return 0 for sanity."""
    return 0


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
    draw_columns06b: bool = False,
    draw_grid: bool = False,
    label_font_size: int = 12,
    stroke_width: float = 1.0,
    pdf_annotations: bool = True,
    render_previews: bool = True,
    # NEW: visual simplifications for quick debugging
    draw_gutter: bool = False,
    # Dual-gutter controls: left shows element kinds; right shows section T endcaps
    gutter_left_tags: bool = False,
    gutter_right_section_caps: bool = False,
    draw_section_plaques: bool = True,
    draw_figure_watermark: bool = False,
    draw_table_callouts: bool = True,
    labels_verbose: bool = False,
    mode: str = "all",  # "structure" | "tables" | "reflow" | "all"
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
    except Exception as exc:
        log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
        raise

    t0 = time.time()
    logger.info(f"09a_pdf_annotator: start → {pdf_path}")

    # Load inputs
    sections = json.loads(sections_json.read_text(encoding="utf-8")).get("sections") or []
    tables = json.loads(tables_json.read_text(encoding="utf-8")).get("tables") or []
    figures = json.loads(figures_json.read_text(encoding="utf-8")).get("figures") or []
    # Map figure_id -> ai_description (if present)
    fig_desc: dict[str, str] = {}
    for f in figures:
        try:
            fid = str(f.get("figure_id")) if f.get("figure_id") is not None else None
            desc = f.get("ai_description") or f.get("description") or ""
            if fid and isinstance(desc, str) and desc.strip():
                fig_desc[fid] = desc.strip()
        except Exception as exc:
            log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
            raise
    reflowed_sections = []
    if reflowed_json is not None:
        try:
            rj = json.loads(reflowed_json.read_text(encoding="utf-8"))
            reflowed_sections = rj.get("reflowed_sections") or rj.get("sections") or []
        except Exception as exc:
            log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
            raise
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
                        block_lookup[str(bid)] = (
                            int(pg),
                            [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])],
                        )
                except Exception as exc:
                    log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                    raise
        except Exception as exc:
            log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
            raise

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
        except Exception as exc:
            log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
            raise

    # Stage 06b layout sketch (optional)
    layout06b: dict[str, Any] | None = None
    if layout06b_json is None:
        auto = output_dir / "06b_layout_sketcher" / "json_output" / "06b_layout_sketch.json"
        if auto.exists():
            layout06b_json = auto
    if layout06b_json is not None and Path(layout06b_json).exists():
        try:
            layout06b = json.loads(Path(layout06b_json).read_text(encoding="utf-8"))
        except Exception as exc:
            log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
            raise

    # Optional: requirements overlays (Stage 07 requirements miner)
    requirements: list[dict[str, Any]] = []
    try:
        req_p = output_dir / "07_requirements_miner" / "json_output" / "07_requirements.json"
        if req_p.exists():
            req_obj = json.loads(req_p.read_text(encoding="utf-8"))
            requirements = req_obj.get("requirements") or []
    except Exception as exc:
        log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
        raise

    # Annotate
    # Safety: do not allow overwriting PDFs under data/input/ or external input paths
    if overwrite_pdf and str(pdf_path).startswith("data/input/"):
        raise ValueError(
            "Refusing to overwrite a source PDF under data/input/. Use a copy or disable --overwrite-pdf."
        )
    doc = fitz.open(str(pdf_path))

    lane_left_by_page: dict[int, fitz.Rect] = {}
    lane_right_by_page: dict[int, fitz.Rect] = {}
    if draw_gutter:
        try:
            for pidx in range(len(doc)):
                try:
                    page = doc[pidx]
                except Exception as exc:
                    log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                    raise
                if gutter_left_tags:
                    lane_left_by_page[pidx] = draw.draw_page_gutter(page, "left")
                if gutter_right_section_caps:
                    lane_right_by_page[pidx] = draw.draw_page_gutter(page, "right")
        except Exception as exc:
            log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
            raise

    # Optional: mode presets (cheap switch for QA)
    try:
        m = (mode or "structure").lower().strip()
        if m == "structure":
            draw_text_chunks = False
            draw_headers03 = False
        elif m == "tables":
            draw_sections = False
            draw_figures = False
            draw_text_chunks = False
            draw_headers03 = False
        elif m == "reflow":
            draw_sections = False
            draw_tables = False
            draw_figures = False
        elif m == "all":
            pass
    except Exception as exc:
        log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
        raise

    # Queue of gutter plaques to render in a final pass (after overlays/grid)
    # {_pg -> [ { "rect": fitz.Rect, "label": str, "color": (r,g,b) }, ... ]}
    pending_left_tags: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    pending_right_tags: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    overlays: list[dict[str, Any]] = []
    overlay_id = 0
    pages_touched: set[int] = set()

    def _normalized_page_index(idx: Any) -> int | None:
        """Normalize a page index, adjusting out-of-bounds values to None."""
        _pg = _coerce_page(idx)
        if _pg is None:
            return None
        if _pg >= len(doc) and (_pg - 1) in range(len(doc)):
            _pg -= 1
        if _pg < 0 or _pg >= len(doc):
            return None
        return _pg

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
        """Register an overlay on a page with its attributes."""
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
        except Exception as exc:
            log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
            raise
            logger.warning(f"Skipping overlay (kind={kind}): non-numeric bbox {bbox}")
            return
        pdf_bbox = [x0, y0, x1, y1]
        rect = _rect_for_kind(page, pdf_bbox, kind)
        stroke_color, fill_color, fill_opacity = _style_for_kind(kind)
        label = _format_label(kind, payload, label_text)
        drew = False
        if pdf_annotations:
            try:
                annot = page.add_rect_annot(rect)
                annot.set_colors(stroke=stroke_color, fill=None)
                try:
                    annot.set_border(width=max(2.5, float(stroke_width)))
                except Exception as exc:
                    log_stage_error("09a_pdf_annotator", exc, {"context": "set_border"})
                try:
                    annot.set_opacity(1.0)
                except Exception as exc:
                    log_stage_error("09a_pdf_annotator", exc, {"context": "set_opacity"})
                try:
                    info = {}
                    if label:
                        info["title"] = str(label)[:120]
                    annot.set_info(info)
                except Exception as exc:
                    log_stage_error("09a_pdf_annotator", exc, {"context": "set_info"})
                # Store compact JSON payload in comment for quick inspection (best-effort)
                try:
                    compact = json.dumps(
                        {k: v for k, v in payload.items() if k not in {"bbox"}}, ensure_ascii=False
                    )
                    if hasattr(annot, "set_contents"):
                        annot.set_contents(compact[:2000])
                except Exception as exc:
                    log_stage_error("09a_pdf_annotator", exc, {"context": "set_contents"})
                annot.update()
                drew = True
            except Exception as exc:
                log_stage_error("09a_pdf_annotator", exc, {"context": "add_rect_annot"})
                drew = False
        if not drew:
            try:
                page.draw_rect(
                    rect,
                    color=stroke_color,
                    width=max(2.5, float(stroke_width)),
                    fill=None,
                    overlay=True,
                )
            except Exception as exc:
                log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                raise
                pass
        try:
            if draw_gutter:
                gutter_label = (label or HUMAN_KIND.get(kind) or "").strip()
                if gutter_left_tags and gutter_label and rect and lane_left_by_page.get(_pg):
                    pending_left_tags[_pg].append(
                        {
                            "rect": rect,
                            "label": gutter_label,
                            "color": (0.12, 0.12, 0.12),
                            "font": 9.0,
                        }
                    )
                if gutter_right_section_caps and kind == "section" and rect:
                    pending_right_tags[_pg].append((rect.y0, rect.y1))
            if kind == "section" and draw_section_plaques:
                _draw_section_title_plaque(
                    page,
                    rect,
                    payload.get("title") or label,
                    stroke=COLORS.get("table", (0.86, 0.25, 0.2)),
                    font=11.0,
                )
            if kind == "figure":
                # Keep only the overlay; captions/watermarks are shown in the data pane.
                pass
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
        except Exception as exc:
            log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
            raise
        if labels and labels_verbose and label:
            draw.draw_label(page, rect, label, stroke_color, float(label_font_size))
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
                    bids = (blk.get("source") or {}).get("block_ids") or []
                    for bid in bids:
                        lookup = block_lookup.get(str(bid))
                        if not lookup:
                            continue
                        pg, bb = lookup
                        per_page.setdefault(pg, []).append(bb)
                for pg, bbs in per_page.items():
                    if not bbs:
                        continue
                    x0 = min(bb[0] for bb in bbs)
                    y0 = min(bb[1] for bb in bbs)
                    x1 = max(bb[2] for bb in bbs)
                    y1 = max(bb[3] for bb in bbs)
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
            logger.warning(
                "09a: no section overlays drawn (check section headers in Stage 04 output)"
            )
        _append_timing(
            logs_dir,
            {
                "stage": "09a_pdf_annotator",
                "event": "draw_sections",
                "latency_ms": int((time.monotonic() - t_s) * 1000),
            },
        )

    # Tables (prefer logical merged tables from reflow when available)
    if draw_tables:
        t_s = time.monotonic()
        drew = 0
        merged_groups = 0
        if prefer_reflow_tables and reflowed_sections:
            groups: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
            for sec in reflowed_sections:
                sid = sec.get("id") or sec.get("section_id")
                for tbl in sec.get("tables") or []:
                    lid = tbl.get("normalized_id") or tbl.get("logical_table_id")
                    title = (tbl.get("title") or tbl.get("caption") or "").strip().lower()
                    key = (
                        lid
                        or f"section:{sid}::table:{tbl.get('table_index') or title or len(groups)}"
                    )
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
                is_contiguous = len(sorted_pages) > 1 and sorted_pages == list(
                    range(sorted_pages[0], sorted_pages[-1] + 1)
                )
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
                layout_dir = (
                    Path(layout06b_json).parent if isinstance(layout06b_json, Path) else None
                )
                v2_path = (
                    (layout_dir / "06b_layout_sketch_v2.json")
                    if (layout_dir and (layout_dir / "06b_layout_sketch_v2.json").exists())
                    else None
                )
                tables_v2 = []
                if v2_path:
                    v2 = json.loads(v2_path.read_text(encoding="utf-8"))
                    for _sid, sv2 in (v2.get("sections") or {}).items():
                        for obj in sv2.get("objects") or []:
                            if obj.get("type") == "table":
                                tables_v2.append(obj)
                else:
                    # fall back to per-section sketch_v2 in layout06b
                    secs = (layout06b.get("sections") or {}) if isinstance(layout06b, dict) else {}
                    for _sid, _sk in secs.items():
                        sv2 = (_sk.get("sketch_v2") or {}) if isinstance(_sk, dict) else {}
                        for obj in sv2.get("objects") or []:
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
                    pages = sorted(
                        {
                            p
                            for p in (
                                _coerce_page(i.get("page_index"), i.get("page")) for i in items
                            )
                            if p is not None
                        }
                    )
                    if len(pages) <= 1:
                        continue
                    if pages != list(range(pages[0], pages[-1] + 1)):
                        continue
                    for p in pages:
                        bbs = [
                            i.get("bbox")
                            for i in items
                            if _coerce_page(i.get("page_index"), i.get("page")) == p
                        ]
                        bbs = [bb for bb in bbs if isinstance(bb, (list, tuple)) and len(bb) == 4]
                        if not bbs:
                            continue
                        x0 = min(bb[0] for bb in bbs)
                        y0 = min(bb[1] for bb in bbs)
                        x1 = max(bb[2] for bb in bbs)
                        y1 = max(bb[3] for bb in bbs)
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
                merged_groups = sum(
                    1
                    for lid, arr in by_lid.items()
                    if len(
                        {
                            p
                            for p in (_coerce_page(i.get("page_index"), i.get("page")) for i in arr)
                            if p is not None
                        }
                    )
                    > 1
                )
                # If still no groups, derive header→body by header_norm non-digit + same cols and horizontal alignment
                if merged_groups == 0 and tables_v2:
                    # index by page
                    by_page: dict[int, list[dict[str, Any]]] = {}
                    for o in tables_v2:
                        p = _coerce_page(o.get("page_index"), o.get("page"))
                        by_page.setdefault(p, []).append(o)

                    def _is_generic(h: str) -> bool:
                        """Validate if string represents a generic ID format."""
                        return bool(h) and all(tok.isdigit() for tok in h.split("|"))

                    def _h_iou(a, b):
                        """Calculate the Intersection over Union (IoU) of two intervals."""
                        try:
                            ax0, _, ax1, _ = a
                            bx0, _, bx1, _ = b
                            inter = max(0.0, min(ax1, bx1) - max(ax0, bx0))
                            uni = max(ax1, bx1) - min(ax0, bx0)
                            return float(inter / uni) if uni > 0 else 0.0
                        except Exception as exc:
                            log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                            raise
                            return 0.0

                    for p, hdrs in by_page.items():
                        nxt = by_page.get(p + 1) or []
                        for h in hdrs:
                            hn = (h.get("header_norm") or "").strip()
                            if not hn or _is_generic(hn):
                                continue
                            cols_h = int(h.get("cols") or 0)
                            for b in nxt:
                                cols_b = int(b.get("cols") or 0)
                                if cols_b != cols_h:
                                    continue
                                if (
                                    _h_iou(
                                        h.get("bbox") or [0, 0, 0, 0], b.get("bbox") or [0, 0, 0, 0]
                                    )
                                    < 0.2
                                ):
                                    continue
                                # draw merged on both pages
                                for pp, oset in ((p, [h]), (p + 1, [b])):
                                    bbx = oset[0].get("bbox") or [0, 0, 0, 0]
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
            except Exception as exc:
                log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                raise
                pass
        if drew == 0 and merged_groups == 0:
            logger.warning("09a: no table overlays drawn (check reflow/table JSON and block ids)")
        _append_timing(
            logs_dir,
            {
                "stage": "09a_pdf_annotator",
                "event": "draw_tables",
                "latency_ms": int((time.monotonic() - t_s) * 1000),
            },
        )

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
                logger.warning(
                    f"09a: skipping figure overlay (page/bbox invalid) fid={f.get('figure_id')} page={f.get('page')}"
                )
        if figs_drawn == 0 and isinstance(figures, list) and len(figures) > 0:
            logger.warning(
                "09a: figures were present but none were drawn — investigate page indices and bboxes"
            )
        _append_timing(
            logs_dir,
            {
                "stage": "09a_pdf_annotator",
                "event": "draw_figures",
                "latency_ms": int((time.monotonic() - t_s) * 1000),
            },
        )

    # Knowledge chunks from Stage 07 reflowed sections
    if draw_text_chunks and reflowed_sections and block_lookup:
        t_s = time.monotonic()
        _text_budget: Dict[int, int] = {}
        for sec in reflowed_sections:
            blocks = sec.get("reflowed_json", {}).get("blocks") or []
            for idx, blk in enumerate(blocks):
                try:
                    src = blk.get("source") or {}
                    bids = src.get("block_ids") or []
                    if not bids:
                        continue
                    btype = str((blk.get("type") or "").lower())
                    if btype == "paragraph":
                        kind = "reflow_paragraph"
                        pref = "PAR"
                    elif btype == "list":
                        kind = "reflow_list"
                        pref = "LST"
                    elif btype == "heading":
                        kind = "reflow_heading"
                        pref = "HDG"
                    elif btype == "table":
                        kind = "reflow_table"
                        pref = "TBLB"
                    elif btype == "figure":
                        kind = "reflow_figure"
                        pref = "FIGB"
                    else:
                        kind = "text_chunk"
                        pref = "TXT"
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
                except Exception as exc:
                    log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                    raise
                    continue
        _append_timing(
            logs_dir,
            {
                "stage": "09a_pdf_annotator",
                "event": "draw_text_chunks",
                "latency_ms": int((time.monotonic() - t_s) * 1000),
            },
        )

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
                is_cond = (
                    bool(r.get("is_conditional"))
                    or ("conditional" in str(r.get("category", "")).lower())
                    or bool(r.get("condition"))
                )
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
            except Exception as exc:
                log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                raise
                continue
        if req_drawn == 0 and isinstance(requirements, list) and len(requirements) > 0:
            logger.warning(
                "09a: requirements present but none were drawn — check anchors/section fallbacks"
            )
        _append_timing(
            logs_dir,
            {
                "stage": "09a_pdf_annotator",
                "event": "draw_requirements",
                "latency_ms": int((time.monotonic() - t_s) * 1000),
            },
        )

    # Fallback merged-table detection using Stage 05 when reflow lacks linkage
    if prefer_reflow_tables and draw_tables and reflowed_sections and merged_groups == 0:
        try:
            # Identify header on page 0 from 05 tables
            t05 = (
                json.loads(Path(tables_json).read_text(encoding="utf-8"))
                if isinstance(tables_json, (str, Path)) and Path(tables_json).exists()
                else {"tables": []}
            )
            tabs05 = t05.get("tables", [])
            page0_tabs = [
                t
                for t in tabs05
                if _coerce_page(t.get("page_index"), t.get("page_idx"), t.get("page")) == 0
            ]
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
                except Exception as exc:
                    log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                    raise
                # Find a best match on page 1 with same column count
                if isinstance(hdr0, list) and hdr0:
                    c0 = len(hdr0)
                    page1_tabs = [
                        t
                        for t in tabs05
                        if _coerce_page(t.get("page_index"), t.get("page_idx"), t.get("page")) == 1
                    ]
                    match = None
                    for t in page1_tabs:
                        try:
                            df = t.get("pandas_df_raw") or t.get("pandas_df")
                            if isinstance(df, list) and df:
                                r0 = df[0]
                                cols = (
                                    list(r0.keys())
                                    if isinstance(r0, dict)
                                    else (r0 if isinstance(r0, list) else [])
                                )
                                if len(cols) == c0:
                                    match = t
                                    break
                        except Exception as exc:
                            log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                            raise
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
        except Exception as exc:
            log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
            raise
            pass

    tabs_summary = {"mode": "none"}
    try:
        tabs = layout.collect_tabs(sections, overlays)
        logger.debug(f"09a tabs collected kinds: {[tab.get('kind') for tab in tabs]}")
        for tab in tabs:
            for pg in tab.get("pages", []):
                pages_touched.add(int(pg))
        tabs_summary = layout.draw_vertical_tabs(doc, tabs)
        logger.debug(f"09a tabs summary: {tabs_summary}")
    except Exception as exc:
        log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
        raise

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
            except Exception as exc:
                log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                raise
                continue
        _append_timing(
            logs_dir,
            {
                "stage": "09a_pdf_annotator",
                "event": "draw_headers03",
                "latency_ms": int((time.monotonic() - t_s) * 1000),
            },
        )

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
                                gx0 = int(c.get("x0", 0))
                                gx1 = int(c.get("x1", 0))
                                x0 = r.x0 + (r.width) * (gx0 / grid_n)
                                x1 = r.x0 + (r.width) * (gx1 / grid_n)
                                band = fitz.Rect(min(x0, x1), r.y0, max(x0, x1), r.y1)
                                try:
                                    if pdf_annotations:
                                        annot = page.add_rect_annot(band)
                                        annot.set_colors(stroke=_color_for_kind("columns"))
                                        try:
                                            annot.set_opacity(0.2)
                                        except Exception as exc:
                                            log_stage_error(
                                                "09a_pdf_annotator", exc, {"context": "09a"}
                                            )
                                            raise
                                            pass
                                        annot.update()
                                    else:
                                        page.draw_rect(
                                            band,
                                            color=_color_for_kind("columns"),
                                            width=0.2,
                                            fill=None,
                                            overlay=True,
                                        )
                                except Exception as exc:
                                    log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                                    raise
                                    page.draw_rect(
                                        band,
                                        color=_color_for_kind("columns"),
                                        width=0.2,
                                        fill=None,
                                        overlay=True,
                                    )
                                if labels:
                                    page.insert_text(
                                        (band.x0 + 2, band.y0 + max(6, int(label_font_size))),
                                        f"COL {c.get('id')}",
                                        fontsize=max(5, int(label_font_size)),
                                        color=_color_for_kind("columns"),
                                    )
                                pages_touched.add(pidx)
                            except Exception as exc:
                                log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                                raise
                                continue
        except Exception as exc:
            log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
            raise
            pass
        _append_timing(
            logs_dir,
            {
                "stage": "09a_pdf_annotator",
                "event": "draw_columns06b",
                "latency_ms": int((time.monotonic() - t_s) * 1000),
            },
        )

    # Stage 05 demoted (table -> text) markers
    try:
        t05 = (
            json.loads(Path(tables_json).read_text(encoding="utf-8"))
            if isinstance(tables_json, (str, Path)) and Path(tables_json).exists()
            else {}
        )
    except Exception as exc:
        log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
        raise
        t05 = {}
    demoted_blocks = (t05.get("demoted_text_blocks") or []) if isinstance(t05, dict) else []
    if demoted_blocks:
        t_s = time.monotonic()
        for b in demoted_blocks:
            try:
                pg = int(b.get("page_idx") if b.get("page_idx") is not None else -1)
                bb = _safe_get_bbox(b)
                (b.get("reason") or "demoted").upper()
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
            except Exception as exc:
                log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                raise
                continue
        _append_timing(
            logs_dir,
            {
                "stage": "09a_pdf_annotator",
                "event": "draw_demoted05",
                "latency_ms": int((time.monotonic() - t_s) * 1000),
            },
        )

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
        except Exception as exc:
            log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
            raise
            pass
        _append_timing(
            logs_dir,
            {
                "stage": "09a_pdf_annotator",
                "event": "draw_grid",
                "latency_ms": int((time.monotonic() - t_s) * 1000),
            },
        )

    # Final gutter pass: draw plaques last so they sit above lanes/overlays
    if draw_gutter:
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
                except Exception as exc:
                    log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                    raise
                    continue
                for it in items:
                    try:
                        rect = it.get("rect")
                        label = str(it.get("label") or "").strip()
                        if not rect or not label:
                            continue
                        draw.draw_gutter_tag(
                            page,
                            lane,
                            rect,
                            label,
                            color=(it.get("color") or (0.12, 0.12, 0.12)),
                            font=float(it.get("font", 9.0)),
                        )
                    except Exception as exc:
                        log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                        raise
            for _pg, caps in sorted(pending_right_tags.items()):
                if not caps:
                    continue
                lane = lane_right_by_page.get(_pg) or lane_left_by_page.get(_pg)
                if not lane:
                    continue
                try:
                    page = doc[_pg]
                except Exception as exc:
                    log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                    raise
                    continue
                for y0, y1 in caps:
                    try:
                        _draw_t_endcaps(page, lane, y0, y1)
                    except Exception as exc:
                        log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                        raise
        except Exception as exc:
            log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
            raise

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
                    except Exception as exc:
                        log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                        raise
                        continue
            finally:
                src.close()
        except Exception as exc:
            log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
            raise
        _append_timing(
            logs_dir,
            {
                "stage": "09a_pdf_annotator",
                "event": "render_previews",
                "latency_ms": int((time.monotonic() - t_s) * 1000),
            },
        )

    # Overlay map bundle for web viewer
    try:
        layout.emit_overlay_map(stage_dir, overlays, pages_touched, PREVIEW_DPI)
    except Exception as exc:
        log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
        raise

    # Write overlay JSON with summary
    try:
        by_kind: Dict[str, int] = {}
        for o in overlays:
            k = str(o.get("kind") or "")
            by_kind[k] = by_kind.get(k, 0) + 1
        # Best-effort merged-table groups count (from label payload)
        merged_groups = 0
        try:
            merged_groups = len(
                {
                    o.get("logical_table_key")
                    for o in overlays
                    if o.get("kind") == "table_merged" and o.get("logical_table_key")
                }
            )
        except Exception as exc:
            log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
            raise
            merged_groups = 0
        header = {
            "summary": {
                "total_overlays": len(overlays),
                "by_kind": by_kind,
                "pages_touched": sorted(int(p) + 1 for p in pages_touched),
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
        (json_dir / "annotations.json").write_text(
            json.dumps(header, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as exc:
        log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
        raise

    # Legend JSON for colors
    try:
        legend = {
            "colors": {k: list(v) for k, v in COLORS.items()},
            "labels": "SEC/TBL/FIG/TXT/PAR/LST/HDG/REQ prefixes map to section/table/figure/text/paragraph/list/heading/requirement respectively. Section spans in left gutter show T (start) and ⊥ (end).",
        }
        (json_dir / "legend.json").write_text(json.dumps(legend, indent=2))
    except Exception as exc:
        log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
        raise

    # Optional: color-aware header overlay directly onto the source PDF
    if rewrite_headers:

        def _parse_hex_color(h: str | None) -> tuple[float, float, float]:
            """Parse a hex color string into an RGB tuple."""
            try:
                if not h:
                    return (0, 0, 0)
                hs = h.lstrip("#")
                return (
                    int(hs[0:2], 16) / 255.0,
                    int(hs[2:4], 16) / 255.0,
                    int(hs[4:6], 16) / 255.0,
                )
            except Exception as exc:
                log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                raise

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
                        color_hex = (s.get("metadata") or {}).get("header_color_hex") or None
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
                        rect = (
                            fitz.Rect(float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3]))
                            & page.rect
                        )
                        if replace_text_layer:
                            try:
                                page.add_redact_annot(rect, fill=None)
                                page.apply_redactions()
                            except Exception as exc:
                                log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                                raise
                        page.insert_textbox(
                            rect, title, fontsize=size, color=color, fontname=fontname, align=0
                        )
                    except Exception as exc:
                        log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                        raise
                target_path = (
                    pdf_path
                    if overwrite_pdf
                    else pdf_path.with_name(pdf_path.stem + "__headers_patched.pdf")
                )
                try:
                    src_doc.save(str(target_path), incremental=True, deflate=True)
                except Exception as exc:
                    log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                    raise
                    tmp = target_path.with_suffix(target_path.suffix + ".tmp")
                    src_doc.save(str(tmp))
                    if overwrite_pdf:
                        try:
                            tmp.replace(target_path)
                        except Exception as exc:
                            log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
                            raise
                            fallback = pdf_path.with_name(pdf_path.stem + "__headers_patched.pdf")
                            tmp.replace(fallback)
                            target_path = fallback
                    else:
                        pass
                logger.info(f"Section headers overlaid in: {target_path}")
        except Exception as exc:
            log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
            raise

    # Artifacts index and timings
    _write_artifacts_index(stage_dir)
    try:
        _append_timing(
            logs_dir,
            {
                "stage": "09a_pdf_annotator",
                "event": "total",
                "latency_ms": int((time.time() - t0) * 1000),
            },
        )
        _summarize_timings(logs_dir)
    except Exception as exc:
        log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
        raise
        pass

    if sink_id is not None:
        try:
            logger.remove(sink_id)
        except Exception as exc:
            log_stage_error("09a_pdf_annotator", exc, {"context": "09a"})
            raise
            pass

    return annotated_pdf


if __name__ == "__main__":
    import sys

    argv = sys.argv[1:]
    if argv and argv[0] == "sanity":
        sys.exit(sanity())
    print("Usage: python -m extractor.pipeline.steps.09a_pdf_annotator sanity")
