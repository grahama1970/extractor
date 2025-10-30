#!/usr/bin/env python3
"""
Stage 09a: PDF Annotator (deterministic, no LLM)

Overlays rectangles for sections, tables, and figures on the clean PDF to aid
visual review and collaboration. Writes an annotated PDF and a JSON index of
all overlays for downstream tooling.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger
import fitz  # PyMuPDF

# No CLI framework; import and call run(...)


def _safe_get_bbox(obj: dict[str, Any]) -> list[float] | None:
    bb = obj.get("bbox") or obj.get("box")
    if not isinstance(bb, (list, tuple)) or len(bb) != 4:
        return None
    try:
        return [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])]
    except Exception:
        return None


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
) -> Path:
    # Decide stage directory name. Prefer running after 07/08/09 when reflowed_json is available.
    tag = stage_tag
    if tag == "auto":
        tag = "09a" if reflowed_json is not None else "06c"
    stage_dir = output_dir / f"{tag}_pdf_annotator"
    stage_dir.mkdir(parents=True, exist_ok=True)
    json_dir = stage_dir / "json_output"
    json_dir.mkdir(exist_ok=True)

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

    # Annotate
    # Safety: do not allow overwriting PDFs under data/input/ or external input paths
    if overwrite_pdf and str(pdf_path).startswith("data/input/"):
        raise ValueError("Refusing to overwrite a source PDF under data/input/. Use a copy or disable --overwrite-pdf.")
    doc = fitz.open(str(pdf_path))
    overlays: list[dict[str, Any]] = []

    def _add(page_idx: int, bbox: list[float], kind: str, payload: dict[str, Any], *, label_text: str | None = None) -> None:
        # Accept 0-based and 1-based page indices; clamp into range
        _pg = int(page_idx)
        if _pg >= len(doc) and _pg - 1 >= 0 and _pg - 1 < len(doc):
            _pg = _pg - 1
        if _pg < 0 or _pg >= len(doc):
            logger.warning(f"Skipping overlay (kind={kind}): out-of-range page {page_idx}")
            return
        page = doc[_pg]
        # Normalize bbox values and clamp to page rect
        try:
            x0, y0, x1, y1 = [float(v) for v in bbox]
        except Exception:
            logger.warning(f"Skipping overlay (kind={kind}): invalid bbox {bbox}")
            return
        rect = fitz.Rect(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)) & page.rect
        # Colors: section=green, table=red, figure=blue, chunk=orange
        color = (0, 1, 0) if kind == "section" else (1, 0, 0) if kind == "table" else (0, 0, 1) if kind == "figure" else (1, 0.5, 0)
        page.draw_rect(rect, color=color, width=1.0, fill=None, overlay=True)
        if labels:
            try:
                txt = label_text or payload.get("title") or payload.get("figure_id") or payload.get("table_index")
                if txt:
                    # Draw a tiny label at the top-left corner of the rect
                    font_size = 6
                    page.insert_text((rect.x0 + 2, rect.y0 + 6), str(txt)[:120], fontsize=font_size, color=color)
            except Exception:
                pass
        overlays.append({"page": _pg, "bbox": [rect.x0, rect.y0, rect.x1, rect.y1], "kind": kind, **payload})

    for s in sections:
        pg0 = int(s.get("page_start") or s.get("page_idx") or -1)
        bb = _safe_get_bbox(s)
        if bb is not None and pg0 >= 0:
            _add(pg0, bb, "section", {"id": s.get("id"), "title": s.get("title")}, label_text=f"SEC {s.get('id')}: {s.get('title')}")

    for t in tables:
        pg = int(t.get("page_index") or t.get("page_idx") or -1)
        bb = _safe_get_bbox(t)
        if bb is not None and pg >= 0:
            # Try to derive a compact header preview for labels/JSON
            headers_preview = None
            try:
                hdrs = t.get("headers")
                if not hdrs:
                    # some variants carry pandas_df/pandas_df_raw
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
            _add(pg, bb, "table", {"table_index": t.get("table_index"), "headers_preview": headers_preview}, label_text=f"TBL {t.get('table_index')} :: {headers_preview or ''}")

    for f in figures:
        pg = int(f.get("page") or f.get("page_idx") or -1)
        bb = _safe_get_bbox(f)
        if bb is not None and pg >= 0:
            fid = f.get("figure_id")
            desc = fig_desc.get(str(fid), "")
            _add(pg, bb, "figure", {"figure_id": fid, "ai_description": desc}, label_text=f"FIG {fid}")

    # Knowledge chunks (from Stage 07 reflowed sections):
    # For each block with source.block_ids, union the underlying Stage 02 block bboxes per page.
    if reflowed_sections and block_lookup:
        for sec in reflowed_sections:
            blocks = (sec.get("reflowed_json", {}).get("blocks") or [])
            for idx, blk in enumerate(blocks):
                try:
                    src = blk.get("source") or {}
                    bids = src.get("block_ids") or []
                    if not bids:
                        continue
                    # Group bboxes by page, then draw union per page for visibility
                    per_page: dict[int, list[list[float]]] = {}
                    for bid in bids:
                        t = block_lookup.get(str(bid))
                        if not t:
                            continue
                        pg, bb = t
                        per_page.setdefault(pg, []).append(bb)
                    for pg, bbs in per_page.items():
                        # Union as the rect covering all bbs
                        x0 = min(bb[0] for bb in bbs)
                        y0 = min(bb[1] for bb in bbs)
                        x1 = max(bb[2] for bb in bbs)
                        y1 = max(bb[3] for bb in bbs)
                        _add(
                            pg,
                            [x0, y0, x1, y1],
                            "text_chunk",
                            {
                                "block_ids_count": len(bbs),
                                "reading_index": idx,
                                "block_kind": blk.get("type") or blk.get("kind"),
                            },
                            label_text=f"TXT {idx}"
                        )
                except Exception:
                    continue

    # Stage 03 overlays: highlight suspicious headers if present
    if headers03:
        for b in headers03:
            try:
                if not (b.get("suspicious_header") or b.get("is_suspicious")):
                    continue
                pg = int(b.get("page_idx") if b.get("page_idx") is not None else b.get("page") or -1)
                bb = _safe_get_bbox(b)
                verdict = b.get("verdict") or ("accept" if b.get("suspicious_header") else "reject")
                lbl = f"HDR {verdict}"
                _add(pg, bb, "header_candidate", {"block_id": b.get("block_id"), "verdict": verdict}, label_text=lbl) if (bb and pg >= 0) else None
            except Exception:
                continue

    # Stage 06b column bands overlay (light cyan bands per column)
    if layout06b and isinstance(layout06b, dict):
        try:
            # layout06b["sections"] is a map; columns are uniform; use grid + columns
            # We'll draw vertical bands per page using grid fractions
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
                                page.draw_rect(band, color=(0, 1, 1), width=0.2, fill=None, overlay=True)
                                # column id label
                                if labels:
                                    page.insert_text((band.x0 + 2, band.y0 + 8), f"COL {c.get('id')}", fontsize=6, color=(0, 1, 1))
                            except Exception:
                                continue
        except Exception:
            pass

    # Optional: draw a light grid for visual debugging
    try:
        if isinstance(grid, int) and grid and grid > 1:
            for pidx in range(len(doc)):
                page = doc[pidx]
                r = page.rect
                step_x = (r.x1 - r.x0) / float(grid)
                step_y = (r.y1 - r.y0) / float(grid)
                # thin gray lines
                color = (0.7, 0.7, 0.7)
                for i in range(1, grid):
                    x = r.x0 + step_x * i
                    page.draw_line(fitz.Point(x, r.y0), fitz.Point(x, r.y1), color=color, width=0.3)
                    y = r.y0 + step_y * i
                    page.draw_line(fitz.Point(r.x0, y), fitz.Point(r.x1, y), color=color, width=0.3)
    except Exception:
        pass

    # Save outputs
    # Add a simple legend page at the end for color semantics
    try:
        legend = doc.new_page(-1, width=400, height=240)
        y = 30
        entries = [
            ((0,1,0), "Section"),
            ((1,0,0), "Table (header preview in label)"),
            ((0,0,1), "Figure (ai_description in JSON)"),
            ((1,0.5,0), "Text chunk (Stage 07 union)"),
            ((0,1,1), "Layout columns (06b bands)"),
            ((1,0,1), "Suspicious Header (Stage 03)")
        ]
        for color, name in entries:
            legend.draw_rect(fitz.Rect(20, y-8, 40, y+8), color=color, width=1.2, fill=None)
            legend.insert_text((50, y+3), name, fontsize=10, color=(0,0,0))
            y += 24
        legend.insert_text((20, y+20), "Labels: SEC/TBL/FIG/TXT/HDR ...", fontsize=9, color=(0,0,0))
    except Exception:
        pass

    annotated_pdf = stage_dir / "annotated.pdf"
    doc.save(str(annotated_pdf))
    doc.close()

    (json_dir / "annotations.json").write_text(
        json.dumps({"overlays": overlays}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Annotated PDF saved: {annotated_pdf}")

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
                        # Color + font style from Stage 04 (if available)
                        color_hex = ((s.get("metadata") or {}).get("header_color_hex") or None)
                        color = _parse_hex_color(color_hex)
                        fsf = (hdr.get("first_span_font") or {}) if isinstance(hdr, dict) else {}
                        # Try to honor original font family and size
                        size = float(fsf.get("size", 0) or 0) or 11.0
                        fname = str(fsf.get("name") or "").lower()
                        # Map common families to built-ins
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
                        # If requested, remove the original header text from the text layer first,
                        # then insert the corrected title (preserving style/color).
                        if replace_text_layer:
                            try:
                                page.add_redact_annot(rect, fill=None)
                                # Apply only text removal; keep images unchanged (default behaviour)
                                page.apply_redactions()
                            except Exception as _e:
                                logger.debug(f"redaction failed on p{pg} rect={rect}: {_e}")
                        # Draw colored title without erasing existing content (or after redaction)
                        page.insert_textbox(rect, title, fontsize=size, color=color, fontname=fontname, align=0)
                    except Exception:
                        continue
                target_path = pdf_path if overwrite_pdf else pdf_path.with_name(pdf_path.stem + "__headers_patched.pdf")
                # Try incremental save; if it fails (e.g., due to encryption/linearization), fall back to full save
                try:
                    src_doc.save(str(target_path), incremental=True, deflate=True)
                except Exception:
                    # Full rewrite via temp file then replace if overwriting
                    tmp = target_path.with_suffix(target_path.suffix + ".tmp")
                    src_doc.save(str(tmp))
                    if overwrite_pdf:
                        try:
                            tmp.replace(target_path)
                        except Exception:
                            # As a fallback, write side-by-side file
                            fallback = pdf_path.with_name(pdf_path.stem + "__headers_patched.pdf")
                            tmp.replace(fallback)
                            target_path = fallback
                    else:
                        # Already a distinct output path
                        pass
                print(f"Section headers overlaid in: {target_path}")
        except Exception as e:
            logger.warning(f"Header rewrite failed (continuing): {e}")


if __name__ == "__main__":
    print("Import and call run(...); no CLI framework required.")
