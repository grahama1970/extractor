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
from extractor.pipeline.utils.reliability import log_stage_error

try:
    from camelot import io as camelot_io
except ImportError:
    camelot_io = None  # type: ignore

STEP_NAME = "05_table_extractor"

# Camelot extraction strategies
CAMELOT_STRATEGIES = {
    "lattice_default": {
        "flavor": "lattice",
        "params": {"process_background": False, "line_scale": 15},
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
}

# Padding ratios for table image extraction
VERTICAL_PADDING_RATIO = float(os.getenv("TABLE_VERTICAL_PADDING_RATIO", 0.30))
HORIZONTAL_PADDING_RATIO = float(os.getenv("TABLE_HORIZONTAL_PADDING_RATIO", 0.07))
PYMUPDF_DPI = int(os.getenv("TABLE_EXTRACTION_DPI", 200))


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
            except Exception:
                pass
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
    import fitz
    
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
        bbox_rect = fitz.Rect(x1_padded, rect_y0, x2_padded, rect_y1)

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
            except Exception:
                pass
        return None


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
    "bbox_tuple_for",
]
