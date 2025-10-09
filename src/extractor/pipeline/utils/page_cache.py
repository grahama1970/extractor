from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Optional


def _pdf_hash(pdf_path: Path) -> str:
    try:
        # Hash file contents for stability
        return hashlib.sha256(pdf_path.read_bytes()).hexdigest()[:12]
    except Exception:
        # Fallback to name-based hash to avoid failures on huge files
        return hashlib.sha256(str(pdf_path).encode("utf-8")).hexdigest()[:12]


def get_cached_page_image(pdf_path: Path, page_index: int, dpi: int, cache_root: Path) -> Path:
    """Render and cache a full page PNG at `dpi`. Returns the image path."""
    cache_root.mkdir(parents=True, exist_ok=True)
    h = _pdf_hash(pdf_path)
    out_dir = cache_root / h
    out_dir.mkdir(exist_ok=True, parents=True)
    out_path = out_dir / f"page_{page_index}_{dpi}.png"
    if out_path.exists():
        return out_path
    import fitz  # type: ignore
    doc = fitz.open(str(pdf_path))
    try:
        if page_index >= len(doc):
            raise IndexError("page_index out of range")
        page = doc[page_index]
        mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        pix = page.get_pixmap(matrix=mat)
        pix.save(out_path)
    finally:
        doc.close()
    return out_path


def crop_from_cached(page_png: Path, page_width: float, page_height: float, bbox: list[float]) -> Optional[bytes]:
    """Crop a bbox (PDF units) from a cached full-page image. Returns PNG bytes or None.

    Requires Pillow; falls back to None if unavailable.
    """
    try:
        from PIL import Image
    except Exception:
        return None
    try:
        img = Image.open(page_png).convert("RGBA")
        w, h = img.size
        sx = w / float(page_width or 1)
        sy = h / float(page_height or 1)
        x0, y0, x1, y1 = bbox
        crop = img.crop((int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy)))
        from io import BytesIO
        buf = BytesIO()
        crop.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None

