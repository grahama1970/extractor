#!/usr/bin/env python3
"""Camelot extraction utilities for Stage 05 (Table Extractor).

Wraps Camelot library calls and strategy configuration.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from extractor.pipeline.utils.diagnostics import make_event

try:
    from camelot import io as camelot_io
except ImportError:
    camelot_io = None  # type: ignore

STEP_NAME = "05_table_extractor"


class _Rect:
    """Lightweight rectangle for pdf_oxide proxy compatibility (replaces fitz.Rect)."""
    __slots__ = ("x0", "y0", "x1", "y1")

    def __init__(self, x0: float, y0: float, x1: float, y1: float):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1

    @property
    def width(self): return self.x1 - self.x0

    @property
    def height(self): return self.y1 - self.y0

# Padding ratios for table image extraction
VERTICAL_PADDING_RATIO = float(os.getenv("TABLE_VERTICAL_PADDING_RATIO", 0.30))
HORIZONTAL_PADDING_RATIO = float(os.getenv("TABLE_HORIZONTAL_PADDING_RATIO", 0.07))
PYMUPDF_DPI = int(os.getenv("TABLE_EXTRACTION_DPI", 200))
CAMELOT_LINE_SCALE_DEFAULT = int(os.getenv("CAMELOT_LINE_SCALE_DEFAULT", 15))

# Camelot extraction strategies
CAMELOT_STRATEGIES = {
    "lattice_default": {
        "flavor": "lattice",
        "params": {"process_background": False, "line_scale": CAMELOT_LINE_SCALE_DEFAULT},
    },
    "lattice_strong": {
        "flavor": "lattice",
        "params": {"process_background": False, "line_scale": 40},
    },
    "lattice_sensitive": {
        "flavor": "lattice",
        "params": {"process_background": False, "line_scale": 5},
    },
    "stream_default": {
        "flavor": "stream",
        "params": {"edge_tol": 50},
    },
    "stream_tight": {
        "flavor": "stream",
        "params": {"edge_tol": 30, "row_tol": 5},
    },
    "stream_wide": {
        "flavor": "stream",
        "params": {"edge_tol": 80, "row_tol": 15},
    },
    "stream_columns": {
        "flavor": "stream",
        "params": {"edge_tol": 50, "column_tol": 10},
    },
}


def try_camelot_strategy(
    pdf_path: Path,
    page_num: int,
    strategy: Dict[str, Any],
    diagnostics: Optional[List[Dict[str, Any]]] = None,
) -> List[Any]:
    """Try a specific Camelot extraction strategy and record diagnostics on failure."""
    if camelot_io is None:
        raise ImportError("Camelot is required for table extraction")

    page_str = str(page_num + 1)  # Camelot uses 1-based page numbers
    try:
        tables = camelot_io.read_pdf(
            str(pdf_path),
            pages=page_str,
            flavor=strategy["flavor"],
            **strategy["params"],
        )
        return list(tables)
    except Exception as e:
        logger.warning(
            f"Strategy '{strategy.get('name', 'unknown')}' failed on page {page_str}: {e}"
        )
        if diagnostics is not None:
            try:
                diagnostics.append(
                    make_event(
                        STEP_NAME,
                        "warning",
                        "camelot_strategy_failed",
                        str(e),
                        {"page": page_num, "strategy": strategy.get("name")},
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to record camelot strategy failure diagnostic: {e}")
        return []


def extract_table_image(
    pdf_doc: Any,
    page_num: int,
    bbox: Tuple[float, float, float, float],
    output_dir: Path,
    table_idx: int,
    diagnostics: Optional[list] = None,
    custom_name: Optional[str] = None,
) -> Optional[str]:
    """Extract table as image with padding.

    Args:
        pdf_doc: fitz.Document object
        page_num: 0-based page number
        bbox: (x1, y1, x2, y2) in Camelot coordinates
        output_dir: Directory to save images
        table_idx: Table index for filename
        diagnostics: Optional list to append errors
        custom_name: Optional custom filename

    Returns:
        Path to saved image or None on error
    """
    try:
        page = pdf_doc[page_num]
        x1, y1, x2, y2 = bbox
        page_height = page.rect.height
        page_width = page.rect.width

        # Add vertical padding
        table_height = y2 - y1
        vpad = table_height * VERTICAL_PADDING_RATIO
        y1_padded = max(0, y1 - vpad)
        y2_padded = min(page_height, y2 + vpad)

        # Add horizontal padding
        table_width = x2 - x1
        hpad = table_width * HORIZONTAL_PADDING_RATIO
        x1_padded = max(0, x1 - hpad)
        x2_padded = min(page_width, x2 + hpad)

        # Convert to PyMuPDF coordinates (origin top-left)
        rect_y0 = page_height - y2_padded
        rect_y1 = page_height - y1_padded
        bbox_rect = _Rect(x1_padded, rect_y0, x2_padded, rect_y1)

        # Render and save
        pix = page.get_pixmap(clip=bbox_rect, dpi=PYMUPDF_DPI)
        filename = custom_name or f"page_{page_num+1}_table_{table_idx+1}.png"
        img_path = output_dir / filename
        pix.save(str(img_path))
        return str(img_path)

    except Exception as e:
        logger.error(f"Failed to extract table image: {e}")
        if diagnostics is not None:
            try:
                diagnostics.append(
                    make_event(
                        STEP_NAME,
                        "error",
                        "image_extract_failed",
                        str(e),
                        {"page": page_num, "table_idx": table_idx},
                    )
                )
            except Exception as e:
                logger.debug(f"Failed to record image extraction failure diagnostic: {e}")
        return None


def extract_page_half_image(
    pdf_path: Path,
    page_index: int,
    half: str,
    dpi: int = 200,
) -> "Image.Image":
    """Render top or bottom half of a PDF page to PIL Image.

    Args:
        pdf_path: Path to PDF file.
        page_index: 0-based page number.
        half: ``"top"`` or ``"bottom"``.
        dpi: Render resolution.

    Returns:
        PIL Image of the requested half (RGB).
    """
    import pdf_oxide
    from PIL import Image as PILImage
    import io

    doc = pdf_oxide.open(str(pdf_path))
    w, h = doc.page_dimensions(page_index)
    mid_y = h / 2.0
    if half == "top":
        clip = (0, 0, w, mid_y)
    elif half == "bottom":
        clip = (0, mid_y, w, h)
    else:
        raise ValueError(f"half must be 'top' or 'bottom', got {half!r}")
    img_bytes = doc.render_page_clipped(page_index, clip, dpi=dpi)
    img = PILImage.open(io.BytesIO(bytes(img_bytes)))
    return img.convert("RGB")


def concat_page_halves(
    pdf_path: Path,
    page_n: int,
    page_n1: int,
    output_path: Optional[Path] = None,
    dpi: int = 200,
    target_size: Tuple[int, int] = (224, 224),
) -> "Image.Image":
    """Concatenate bottom of page N + top of page N+1 side-by-side.

    This follows the PubTables-v2 approach: the two halves are placed
    side-by-side and resized to *target_size* so a standard vision
    classifier can consume them.

    Args:
        pdf_path: Path to PDF.
        page_n: 0-based index of the first page.
        page_n1: 0-based index of the second page.
        output_path: If given, save the result as PNG.
        dpi: Render resolution.
        target_size: Final (width, height) after resize.

    Returns:
        PIL Image (RGB) of the combined halves.
    """
    from PIL import Image as PILImage

    bottom = extract_page_half_image(pdf_path, page_n, "bottom", dpi=dpi)
    top = extract_page_half_image(pdf_path, page_n1, "top", dpi=dpi)

    # Normalise both halves to a common height before pasting
    target_h = max(bottom.height, top.height)
    if bottom.height != target_h:
        ratio = target_h / bottom.height
        bottom = bottom.resize((int(bottom.width * ratio), target_h))
    if top.height != target_h:
        ratio = target_h / top.height
        top = top.resize((int(top.width * ratio), target_h))

    combined = PILImage.new("RGB", (bottom.width + top.width, target_h))
    combined.paste(bottom, (0, 0))
    combined.paste(top, (bottom.width, 0))

    # Resize to standard classifier input
    combined = combined.resize(target_size)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        combined.save(str(output_path))

    return combined


def pre_rasterize_page(
    pdf_path: Path,
    page_num: int,
    output_dir: Path,
    dpi: int = 300,
) -> Path:
    """Render a PDF page to PNG once via PyMuPDF.

    Used to avoid re-rasterizing the same page when retrying
    multiple lattice strategies (which differ only in OpenCV
    line_scale params, not the source raster).

    Args:
        pdf_path: Path to the PDF.
        page_num: 0-based page number.
        output_dir: Directory for temp PNG.
        dpi: Render resolution.

    Returns:
        Path to the cached PNG file.
    """
    import pdf_oxide

    png_path = output_dir / f"_raster_p{page_num}.png"
    if png_path.exists():
        return png_path

    doc = pdf_oxide.open(str(pdf_path))
    img_bytes = doc.render_page(page_num, dpi=dpi)
    png_path.write_bytes(bytes(img_bytes))
    return png_path


def cleanup_raster_cache(output_dir: Path, page_num: int) -> None:
    """Remove the cached raster PNG for a page."""
    png_path = output_dir / f"_raster_p{page_num}.png"
    try:
        png_path.unlink(missing_ok=True)
    except OSError as e:
        logger.debug(f"Failed to clean up raster cache {png_path}: {e}")


def bbox_tuple_for(table_obj: Any) -> Optional[Tuple[float, float, float, float]]:
    """Extract bbox tuple from a Camelot table object."""
    bt = getattr(table_obj, "_bbox", None)
    if not bt and hasattr(table_obj, "cells") and getattr(table_obj, "cells"):
        try:
            xs = [c.x1 for c in table_obj.cells] + [c.x2 for c in table_obj.cells]
            ys = [c.y1 for c in table_obj.cells] + [c.y2 for c in table_obj.cells]
            bt = (min(xs), min(ys), max(xs), max(ys))
        except Exception:
            bt = None
    return bt


__all__ = [
    "CAMELOT_STRATEGIES",
    "VERTICAL_PADDING_RATIO",
    "HORIZONTAL_PADDING_RATIO",
    "PYMUPDF_DPI",
    "try_camelot_strategy",
    "extract_table_image",
    "extract_page_half_image",
    "concat_page_halves",
    "bbox_tuple_for",
]
