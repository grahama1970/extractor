"""Shared pdf_oxide rendering helpers — replaces all fitz/PyMuPDF rendering calls.

Provides a thin wrapper around pdf_oxide's render_page and render_page_clipped
so that pipeline steps can render page regions without importing fitz.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional, Tuple

from loguru import logger


class OxideRenderer:
    """Wraps a pdf_oxide.PdfDocument for rendering operations.

    Usage:
        renderer = OxideRenderer(pdf_path)
        png_bytes = renderer.render_page(0, dpi=144)
        png_bytes = renderer.render_clipped(0, bbox=[x0, y0, x1, y1], dpi=144)
        renderer.close()
    """

    def __init__(self, pdf_path: str | Path):
        import pdf_oxide

        self._doc = pdf_oxide.PdfDocument(str(pdf_path))
        self._page_count = self._doc.page_count()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass  # pdf_oxide handles cleanup via drop

    @property
    def page_count(self) -> int:
        return self._page_count

    def page_dimensions(self, page_idx: int) -> Tuple[float, float]:
        """Return (width, height) in points for a page."""
        return self._doc.page_dimensions(page_idx)

    def render_page(self, page_idx: int, dpi: int = 144) -> bytes:
        """Render a full page to PNG bytes."""
        return self._doc.render_page(page_idx, dpi=dpi)

    def render_clipped(
        self,
        page_idx: int,
        bbox: list | tuple,
        dpi: int = 144,
    ) -> bytes:
        """Render a clipped region of a page to PNG bytes.

        Args:
            page_idx: Zero-based page index.
            bbox: [x0, y0, x1, y1] in PDF points (origin at top-left).
            dpi: Resolution (default 144 = 2x zoom at 72dpi).
        """
        x0, y0, x1, y1 = [float(v) for v in bbox]
        return self._doc.render_page_clipped(page_idx, x0, y0, x1, y1, dpi=dpi)

    def render_page_to_pil(self, page_idx: int, dpi: int = 144):
        """Render a full page and return as PIL Image."""
        from PIL import Image

        png_bytes = self.render_page(page_idx, dpi=dpi)
        return Image.open(io.BytesIO(png_bytes))

    def render_clipped_to_pil(self, page_idx: int, bbox: list | tuple, dpi: int = 144):
        """Render a clipped region and return as PIL Image."""
        from PIL import Image

        png_bytes = self.render_clipped(page_idx, bbox, dpi=dpi)
        return Image.open(io.BytesIO(png_bytes))

    def save_page_png(self, page_idx: int, output_path: Path, dpi: int = 144) -> bool:
        """Render a page and save as PNG. Returns True on success."""
        try:
            png_bytes = self.render_page(page_idx, dpi=dpi)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(png_bytes)
            return True
        except Exception as e:
            logger.debug(f"Failed to render page {page_idx}: {e}")
            return False

    def save_clipped_png(
        self, page_idx: int, bbox: list | tuple, output_path: Path, dpi: int = 144
    ) -> bool:
        """Render a clipped region and save as PNG. Returns True on success."""
        try:
            png_bytes = self.render_clipped(page_idx, bbox, dpi=dpi)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(png_bytes)
            return True
        except Exception as e:
            logger.debug(f"Failed to render clipped region on page {page_idx}: {e}")
            return False


def get_renderer(pdf_path: str | Path) -> Optional[OxideRenderer]:
    """Safely create an OxideRenderer, returning None on failure."""
    try:
        return OxideRenderer(pdf_path)
    except Exception as e:
        logger.warning(f"Failed to create OxideRenderer for {pdf_path}: {e}")
        return None
