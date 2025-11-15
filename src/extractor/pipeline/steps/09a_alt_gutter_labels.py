"""Alternate Stage 09a: left-gutter labels only.

This step is intentionally minimal. It reads an annotated PDF along with the
overlay metadata (the same `annotations.json` that the primary 09a step emits)
and replays only the left-gutter labels so we can debug plaque rendering in
isolation.

Inputs
------
- `pdf_path`: source PDF to annotate in-place (a copy is written).
- `annotations_json`: the JSON file containing overlays with `_label` fields.

Outputs live under `data/results/pipeline/09a_alt_gutter/` by default.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Iterable

import fitz  # PyMuPDF
from loguru import logger

PLAQUE_FONT_NAME = "helv"
PLAQUE_FONT_MIN = 5.5
PLAQUE_PAD_X = 6.0
PLAQUE_PAD_Y = 4.0
GUTTER_WIDTH = 84.0
GUTTER_PAD = 8.0
PLAQUE_FILL = (0.97, 0.99, 1.0)
PLAQUE_BORDER = (0.62, 0.72, 0.84)


def _text_width(text: str, fontsize: float) -> float:
    """Return approximate text width for the configured plaque font."""

    normalized = (text or "").strip()
    if not normalized:
        return 0.0
    try:
        return float(
            fitz.get_text_length(normalized, fontname=PLAQUE_FONT_NAME, fontsize=fontsize)
        )
    except AttributeError:
        # Older PyMuPDF releases omit `get_text_length`; fall back to a cached
        # Font helper when possible. Avoid expensive instantiation per call.
        font = getattr(_text_width, "_font", None)
        if font is None:
            try:
                font = fitz.Font(fontname=PLAQUE_FONT_NAME)
            except Exception:
                font = None
            _text_width._font = font  # type: ignore[attr-defined]
        if font is not None:
            return float(font.text_length(normalized, fontsize=fontsize))
    # Coarse fallback – ensures we never crash even if PyMuPDF changes again.
    return max(len(normalized), 1) * fontsize * 0.55


def _draw_page_gutter(page: fitz.Page) -> fitz.Rect:
    """Return the left gutter lane (no fill/stroke)."""
    rect = page.rect
    return fitz.Rect(rect.x0 + 6, rect.y0 + 6, rect.x0 + 6 + GUTTER_WIDTH, rect.y1 - 6)


def _draw_gutter_tag(
    page: fitz.Page,
    lane: fitz.Rect,
    target: fitz.Rect,
    text: str,
    color=(0.12, 0.12, 0.12),
    font: float = 9.0,
) -> bool:
    """Draw a single text plaque inside the gutter. Returns True if drawn."""

    if not text or lane is None:
        return False
    label = text.strip()
    if not label:
        return False
    txt_w = _text_width(label, font)
    max_w = max(12.0, lane.width - 2 * GUTTER_PAD)
    font_size = font
    while txt_w > max_w and font_size > PLAQUE_FONT_MIN:
        font_size -= 0.8
        txt_w = _text_width(label, font_size)
    if txt_w > max_w:
        # Ellipsize
        trimmed = label
        while txt_w > max_w and len(trimmed) > 3:
            trimmed = trimmed[:-1]
            txt_w = _text_width(trimmed + "…", font_size)
        label = trimmed + "…" if len(trimmed) > 3 else trimmed
        txt_w = _text_width(label, font_size)
    plaque_h = font_size * 1.7
    cy = target.y0 + target.height / 2.0
    top = max(lane.y0 + GUTTER_PAD, min(cy - plaque_h / 2.0, lane.y1 - GUTTER_PAD - plaque_h))
    left = lane.x0 + GUTTER_PAD
    plaque_w = txt_w + 2 * PLAQUE_PAD_X
    plaque = fitz.Rect(left, top, left + plaque_w, top + plaque_h)
    try:
        annot = page.add_freetext_annot(
            plaque,
            label,
            fontsize=font_size,
            fontname=PLAQUE_FONT_NAME,
            text_color=color,
            fill_color=PLAQUE_FILL,
        )
        try:
            annot.set_border(width=0.6)
            annot.set_colors(stroke=PLAQUE_BORDER)
            annot.set_opacity(0.98)
            annot.update()
        except Exception:
            pass
    except Exception:
        page.draw_rect(plaque, fill=PLAQUE_FILL, color=PLAQUE_BORDER, width=0.6, overlay=True)
        page.insert_text(
            (plaque.x0 + PLAQUE_PAD_X, plaque.y0 + font_size * 1.2 - 1),
            label,
            fontsize=font_size,
            fontname=PLAQUE_FONT_NAME,
            color=color,
            overlay=True,
        )
    return True


def _normalized_rect(values: Iterable[float]) -> fitz.Rect | None:
    try:
        x0, y0, x1, y1 = [float(v) for v in values]
        if x1 <= x0 or y1 <= y0:
            return None
        return fitz.Rect(x0, y0, x1, y1)
    except Exception:
        return None


def _load_overlays(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("overlays") or []


def run(
    pdf_path: Path,
    annotations_json: Path,
    output_dir: Path = Path("data/results/pipeline"),
    *,
    render_previews: bool = True,
) -> Path:
    stage_dir = output_dir / "09a_alt_gutter"
    stage_dir.mkdir(parents=True, exist_ok=True)
    vis_dir = stage_dir / "visual_output"
    vis_dir.mkdir(exist_ok=True)
    log_path = stage_dir / "stage.log"
    logger.add(str(log_path), level="DEBUG", rotation="2 MB", retention=3)

    t0 = time.time()
    logger.info("09a_alt_gutter: start → {pdf}", pdf=pdf_path)
    overlays = _load_overlays(annotations_json)
    if not overlays:
        raise ValueError(f"No overlays found in {annotations_json}")

    doc = fitz.open(str(pdf_path))
    pages_touched: set[int] = set()
    drawn = 0
    skipped = 0

    for ov in overlays:
        page_idx = int(ov.get("page", -1))
        if page_idx < 0 or page_idx >= len(doc):
            logger.debug("skip_overlay_out_of_range", overlay_page=page_idx)
            skipped += 1
            continue
        label = (ov.get("_label") or ov.get("kind") or "").strip()
        if not label:
            logger.debug("skip_overlay_missing_label", overlay_id=ov.get("id"))
            skipped += 1
            continue
        bbox = ov.get("render_bbox") or ov.get("bbox")
        rect = _normalized_rect(bbox or [])
        if rect is None:
            logger.debug("skip_overlay_invalid_bbox", overlay_id=ov.get("id"), bbox=bbox)
            skipped += 1
            continue
        page = doc[page_idx]
        lane = _draw_page_gutter(page)
        if _draw_gutter_tag(page, lane, rect, label):
            drawn += 1
            pages_touched.add(page_idx)
            logger.debug(
                "gutter_label_drawn",
                page=page_idx + 1,
                label=label,
                bbox=list(rect),
            )
        else:
            logger.debug("skip_overlay_draw_failure", page=page_idx + 1, label=label)
            skipped += 1

    annotated_pdf = stage_dir / "annotated.pdf"
    doc.save(str(annotated_pdf))
    doc.close()

    if render_previews and pages_touched:
        src = fitz.open(str(annotated_pdf))
        scale = 144 / 72.0
        mat = fitz.Matrix(scale, scale)
        for page_idx in sorted(pages_touched):
            page = src[page_idx]
            pix = page.get_pixmap(matrix=mat, alpha=False)
            out_png = vis_dir / f"page_{page_idx+1:04d}.png"
            pix.save(str(out_png))
        src.close()

    logger.info(
        "09a_alt_gutter: done in {ms} ms (drawn={drawn}, skipped={skipped})",
        ms=int((time.time() - t0) * 1000),
        drawn=drawn,
        skipped=skipped,
    )
    return annotated_pdf


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Left-gutter labels only annotator")
    parser.add_argument("pdf", type=Path, help="Source PDF")
    parser.add_argument("annotations", type=Path, help="Path to annotations.json")
    parser.add_argument("--output-dir", type=Path, default=Path("data/results/pipeline"))
    parser.add_argument("--no-previews", action="store_true", help="Skip PNG previews")
    args = parser.parse_args()

    run(
        args.pdf,
        args.annotations,
        output_dir=args.output_dir,
        render_previews=not args.no_previews,
    )
