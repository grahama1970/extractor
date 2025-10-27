from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple, Optional

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont


@dataclass
class Box:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    label: str = ""
    color: Tuple[int, int, int] = (255, 0, 0)
    width: int = 3


def _page_image(doc: fitz.Document, page_num: int, dpi: int = 144) -> Image.Image:
    page = doc.load_page(page_num)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pm = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", [pm.width, pm.height], pm.samples)
    return img


def _scale_bbox(b: Box, scale: float, page_height_px: int, y_flip: bool) -> Tuple[int, int, int, int]:
    x0 = int(b.x0 * scale)
    x1 = int(b.x1 * scale)
    if y_flip:
        # flip Y if input uses bottom-left origin
        y0 = int((page_height_px / scale - b.y1) * scale)
        y1 = int((page_height_px / scale - b.y0) * scale)
    else:
        y0 = int(b.y0 * scale)
        y1 = int(b.y1 * scale)
    return x0, y0, x1, y1


def draw_overlays(
    pdf_path: Path,
    boxes: Iterable[Box],
    out_dir: Path,
    *,
    dpi: int = 144,
    y_flip: bool = False,
    font: Optional[ImageFont.FreeTypeFont] = None,
) -> None:
    """Render annotated PNGs with rectangular overlays per page.

    - Groups boxes by page and draws colored rectangles + labels.
    - Saves files as page_###.png in out_dir.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    try:
        page_to_boxes: dict[int, list[Box]] = {}
        for b in boxes:
            page_to_boxes.setdefault(b.page, []).append(b)

        for pno, items in page_to_boxes.items():
            base = _page_image(doc, pno, dpi=dpi)
            draw = ImageDraw.Draw(base)
            page_px_h = base.height
            scale = dpi / 72.0
            for b in items:
                x0, y0, x1, y1 = _scale_bbox(b, scale, page_px_h, y_flip)
                draw.rectangle([x0, y0, x1, y1], outline=b.color, width=b.width)
                if b.label:
                    # draw label background for readability (Pillow 10+: use textbbox)
                    margin = 2
                    try:
                        bbox = draw.textbbox((0, 0), b.label, font=font)
                        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    except Exception:
                        # Fallback approximate sizes
                        tw, th = len(b.label) * 6, 10
                    bg = (0, 0, 0)
                    draw.rectangle([x0, max(0, y0 - th - 2 * margin), x0 + tw + 2 * margin, y0], fill=bg)
                    draw.text((x0 + margin, y0 - th - margin), b.label, fill=(255, 255, 255), font=font)

            out_path = out_dir / f"page_{pno:03d}.png"
            base.save(out_path)
    finally:
        doc.close()
