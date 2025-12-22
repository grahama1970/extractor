#!/usr/bin/env python3
"""Shared pure helpers for Stage 06 figure extraction.

Only include stable, side‑effect‑free utilities. Keep LLM/CLI logic in the
stage file to avoid accidental coupling.
"""
from __future__ import annotations

from extractor.pipeline.utils.reliability import log_stage_error
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple

import fitz  # PyMuPDF


def _estimate_bbox(page: "fitz.Page", block: dict[str, Any]) -> list[float]:
    """Best-effort bbox from block or first image on page."""
    bbox = block.get("bbox")
    if bbox and bbox != [0, 0, 0, 0]:
        return list(map(float, bbox))
    image_list = page.get_images(full=True)
    if image_list:
        rects = page.get_image_rects(image_list[0][0])
        if rects:
            r = rects[0]
            return [float(r.x0), float(r.y0), float(r.x1), float(r.y1)]
    w, h = page.rect.width, page.rect.height
    return [50.0, 100.0, float(w - 50), float(h - 100)]


def _expand_bbox(bbox: Iterable[float], page_h: float, ratio: float) -> list[float]:
    x0, y0, x1, y1 = map(float, bbox)
    pad = (y1 - y0) * ratio
    return [x0, max(0.0, y0 - pad), x1, min(page_h, y1 + pad)]


def _render_region(page: "fitz.Page", bbox: Iterable[float], scale: float = 2.0) -> bytes:
    rect = fitz.Rect(*bbox)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=rect)
    return pix.tobytes("png")


def _save_image_bytes(dst_dir: Path, figure_id: str, data: bytes) -> Path:
    p = dst_dir / f"{figure_id}.png"
    p.write_bytes(data)
    return p


def _nearby_text(page: "fitz.Page", bbox: Iterable[float]) -> str:
    rect = fitz.Rect(*bbox)
    blocks = page.get_text("blocks")
    lines = [b[4].strip() for b in blocks if fitz.Rect(b[:4]).intersects(rect) and (b[4] or "").strip()]
    return " ".join(lines)


def _bbox_area(bbox: Iterable[float]) -> int:
    x0, y0, x1, y1 = map(float, bbox)
    try:
        return int((x1 - x0) * (y1 - y0))
    except Exception as exc:
        log_stage_error('figure_extractor_utils.py', exc, {'context': 'figure_extractor_utils.py'})
        raise
        return 0


def _normalize_title(title: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    import re as _re
    if not title:
        return None, None, None
    m = _re.match(r"\s*(?:Figure|Fig\.)\s*([A-Za-z0-9\-\.]+)?[\.:]?\s*(.*)$", title, _re.IGNORECASE)
    number = (m.group(1) or "").strip() or None if m else None
    base_title = (m.group(2) or "").strip() if m else title
    normalized_id = None
    if number:
        normalized_id = f"figure-{number}"
    elif base_title:
        import hashlib as _hash
        slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in base_title).strip("-")
        normalized_id = f"figure-{slug or _hash.sha1(base_title.encode('utf-8')).hexdigest()[:8]}"
    return number, base_title, normalized_id


def _assemble_result(
    *,
    figure_id: str,
    page_num: int,
    output_dir: Path,
    img_path: Path,
    expanded_bbox: Iterable[float],
    description: str,
    title: Optional[str],
    title_source: Optional[str],
    number: Optional[str],
    base_title: Optional[str],
    normalized_id: Optional[str],
    metadata: Optional[dict] = None,
    extraction_time: Optional[str] = None,
) -> dict[str, Any]:
    bbox_list = [
        float(expanded_bbox[0]),
        float(expanded_bbox[1]),
        float(expanded_bbox[2]),
        float(expanded_bbox[3]),
    ]
    out = {
        "figure_id": figure_id,
        "page": page_num,
        "image_path": str(img_path.relative_to(output_dir.parent.parent)),
        "bbox": bbox_list,
        "ai_description": description,
        "title": title,
        "title_source": title_source,
        "number": number,
        "base_title": base_title,
        "normalized_id": normalized_id,
    }
    if metadata:
        out["metadata"] = metadata
    if extraction_time:
        out["extraction_time"] = extraction_time
    return out


def detect_title_local(
    pdf_path: Path,
    page_idx: int,
    bbox: Iterable[float],
    band_above_px: int = 120,
    band_below_px: int = 140,
) -> Tuple[Optional[str], Optional[str]]:
    """Scan a narrow band above/below the bbox for a caption-like line.

    Returns (title_text, source) where source is "above"|"below" or None.
    Side‑effect free; opens the PDF for the page, reads text blocks, and closes it.
    """
    import re as _re
    try:
        with fitz.open(str(pdf_path)) as _doc:
            page = _doc[page_idx]
            rr = fitz.Rect(*bbox)
            # Below band
            band_below = fitz.Rect(rr.x0, rr.y1, rr.x1, min(page.rect.height, rr.y1 + band_below_px))
            blks = page.get_text("blocks", clip=band_below)
            for b in sorted(blks, key=lambda x: x[1]):
                txt = (b[4] or "").strip()
                if not txt:
                    continue
                if _re.match(r"^\s*(Figure|Fig\.)\s*([A-Za-z0-9\-\.]+)?[\.:]?\s*(.*)$", txt, _re.IGNORECASE):
                    return txt, "below"
            # Above band
            band_above = fitz.Rect(rr.x0, max(0, rr.y0 - band_above_px), rr.x1, rr.y0)
            blks2 = page.get_text("blocks", clip=band_above)
            for b in sorted(blks2, key=lambda x: -x[3]):
                txt = (b[4] or "").strip()
                if not txt:
                    continue
                if _re.match(r"^\s*(Figure|Fig\.)\s*([A-Za-z0-9\-\.]+)?[\.:]?\s*(.*)$", txt, _re.IGNORECASE):
                    return txt, "above"
    except Exception as exc:
        log_stage_error('figure_extractor_utils.py', exc, {'context': 'figure_extractor_utils.py'})
        raise
    return None, None


def intersect_sections(figures: list[dict], sections: list[dict]) -> None:
    """Attach section_id to each figure when its bbox intersects a section bbox on overlapping pages.

    Mutates `figures` in place. Ignores malformed entries gracefully.
    """
    for figure in figures:
        try:
            bbox = figure.get("bbox")
            page = figure.get("page")
            if not bbox or page is None:
                continue
            fb = fitz.Rect(bbox)  # type: ignore[arg-type]
            for s in sections:
                ps = s.get("page_start")
                pe = s.get("page_end")
                sb = s.get("bbox")
                if ps is None or pe is None or sb is None:
                    continue
                if ps <= page <= pe:
                    if fitz.Rect(sb).intersects(fb):  # type: ignore[arg-type]
                        figure["section_id"] = s.get("id", "unknown")
                        break
        except Exception as exc:
            log_stage_error('figure_extractor_utils.py', exc, {'context': 'figure_extractor_utils.py'})
            raise
            continue
