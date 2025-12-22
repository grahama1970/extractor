"""Reflow utilities package for Stage 07.

This package extracts pure utility functions from 07_reflow_section.py
to reduce file size and enable reuse.
"""

from extractor.pipeline.utils.reflow.tables import (
    sanitize_table_cell,
    normalize_table_text,
    df_map,
    compute_table_confidence,
    compute_table_merges,
    build_table_block_from_stage05,
)
from extractor.pipeline.utils.reflow.layout import (
    iou_rect,
    build_figure_block_from_stage06,
)

__all__ = [
    # Tables
    "sanitize_table_cell",
    "normalize_table_text",
    "df_map",
    "compute_table_confidence",
    "compute_table_merges",
    "build_table_block_from_stage05",
    # Layout
    "iou_rect",
    "build_figure_block_from_stage06",
]
