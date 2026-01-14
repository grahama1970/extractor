"""Tables utilities package for Stage 05.

Extracts table processing functions from 05_table_extractor.py.
"""

# Extraction
from extractor.pipeline.utils.tables.extraction import (
    CAMELOT_STRATEGIES,
    VERTICAL_PADDING_RATIO,
    HORIZONTAL_PADDING_RATIO,
    PYMUPDF_DPI,
    try_camelot_strategy,
    extract_table_image,
    bbox_tuple_for,
)

# Metrics
from extractor.pipeline.utils.tables.metrics import (
    generate_pandas_metrics,
    score_table,
    iou,
    horizontal_iou,
    sanitize_cell,
    fragmentation_score,
    should_retry_fragmentation,
    has_fragmentation_improvement,
    should_replace_table,
)

# Heuristics
from extractor.pipeline.utils.tables.heuristics import (
    is_header_row_table,
    stitch_headers,
    detect_table_caption,
    demote_table_headers_to_text,
    demote_sentence_like_single_row_tables,
    demote_text_heavy_lattice_tables,
    coalesce_repeated_header_rows,
)

__all__ = [
    # Extraction
    "CAMELOT_STRATEGIES",
    "VERTICAL_PADDING_RATIO",
    "HORIZONTAL_PADDING_RATIO",
    "PYMUPDF_DPI",
    "try_camelot_strategy",
    "extract_table_image",
    "bbox_tuple_for",
    # Metrics
    "generate_pandas_metrics",
    "score_table",
    "iou",
    "horizontal_iou",
    "sanitize_cell",
    "fragmentation_score",
    "should_retry_fragmentation",
    "has_fragmentation_improvement",
    "should_replace_table",
    # Heuristics
    "is_header_row_table",
    "stitch_headers",
    "detect_table_caption",
    "demote_table_headers_to_text",
    "demote_sentence_like_single_row_tables",
    "demote_text_heavy_lattice_tables",
    "coalesce_repeated_header_rows",
]
