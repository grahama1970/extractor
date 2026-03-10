from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

try:
    import fitz  # PyMuPDF (optional — regression testing only)
except ImportError:
    fitz = None  # type: ignore[assignment]
from PIL import Image, ImageDraw, ImageFont


@dataclass
class Box:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    label: str = ""
    color: Tuple[int, int, int] = (0, 200, 0)


def _to_pixels(
    x: float, y: float, scale: float, page_h_pts: float, y_flip: bool
) -> Tuple[int, int]:
    if y_flip:
        y = page_h_pts - y
    return int(round(x * scale)), int(round(y * scale))


def draw_overlays(
    pdf_path: Path,
    boxes: Iterable[Box],
    out_dir: Path,
    *,
    dpi: int = 144,
    y_flip: bool = False,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    scale = dpi / 72.0
    by_page: dict[int, list[Box]] = {}
    for b in boxes:
        by_page.setdefault(int(b.page), []).append(b)

    font = None
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for pidx in range(len(doc)):
        page = doc[pidx]
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        draw = ImageDraw.Draw(img, "RGBA")
        page_boxes = by_page.get(pidx, [])
        if not page_boxes:
            # still write the page to keep navigation simple
            out = out_dir / f"page_{pidx:03d}.png"
            img.save(out)
            continue
        for b in page_boxes:
            x0, y0 = _to_pixels(b.x0, b.y0, scale, page.rect.height, y_flip)
            x1, y1 = _to_pixels(b.x1, b.y1, scale, page.rect.height, y_flip)
            # Ensure proper ordering
            x0, x1 = min(x0, x1), max(x0, x1)
            y0, y1 = min(y0, y1), max(y0, y1)
            # Rectangle with translucent fill and solid stroke
            r, g, bl = b.color
            draw.rectangle([x0, y0, x1, y1], outline=(r, g, bl, 255), width=3)
            draw.rectangle([x0, y0, x1, y1], fill=(r, g, bl, 40))
            if b.label:
                txt = b.label[:80]
                tw, th = draw.textbbox((0, 0), txt, font=font)[2:4] if font else (0, 0)
                pad = 3
                bx0, by0 = x0, max(0, y0 - th - 2 * pad)
                bx1, by1 = x0 + tw + 2 * pad, by0 + th + 2 * pad
                draw.rectangle([bx0, by0, bx1, by1], fill=(0, 0, 0, 160))
                draw.text((bx0 + pad, by0 + pad), txt, fill=(255, 255, 255, 255), font=font)
        out = out_dir / f"page_{pidx:03d}.png"
        img.save(out)
