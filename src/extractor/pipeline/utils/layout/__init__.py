"""Layout utilities package for Stage 06b.

Extracts layout sketching functions from 06b_layout_sketcher.py.
"""

# Geometry
from extractor.pipeline.utils.layout.geometry import (
    norm,
    grid_bbox,
    area,
    aspect,
    iou,
    horizontal_iou,
    summ,
    norm_text,
    text_sha1,
    union_bbox,
)

# Columns
from extractor.pipeline.utils.layout.columns import (
    detect_columns,
    assign_cols_and_span,
    col_id_for,
)

__all__ = [
    # Geometry
    "norm",
    "grid_bbox",
    "area",
    "aspect",
    "iou",
    "horizontal_iou",
    "summ",
    "norm_text",
    "text_sha1",
    "union_bbox",
    # Columns
    "detect_columns",
    "assign_cols_and_span",
    "col_id_for",
]
