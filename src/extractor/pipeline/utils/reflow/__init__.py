"""Reflow utilities package for Stage 07.

This package extracts pure utility functions from 07_reflow_section.py
to reduce file size (~5400 lines → ~500 lines) and enable reuse.
"""

# Tables
from extractor.pipeline.utils.reflow.tables import (
    sanitize_table_cell,
    normalize_table_text,
    df_map,
    compute_table_confidence,
    compute_table_merges,
    build_table_block_from_stage05,
)

# Layout
from extractor.pipeline.utils.reflow.layout import (
    iou_rect,
    horizontal_iou,
    build_figure_block_from_stage06,
    apply_layout_ordering,
)

# LLM Helpers
from extractor.pipeline.utils.reflow.llm_helpers import (
    extract_router_content,
    content_to_json_dict,
    direct_scillm_json,
    get_usage_field,
)
from extractor.pipeline.utils.reflow.llm import call_reflow_llm

# Prompts
from extractor.pipeline.utils.reflow.prompts import (
    build_reflow_prompt,
    build_compact_prompt,
    build_compact_prompt_simple,
)

# Data Loader
from extractor.pipeline.utils.reflow.data_loader import (
    merge_text_blocks,
    get_rows_cols,
    compute_metrics_for_df,
    merge_section_tables,
    consolidate_data,
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
    "horizontal_iou",
    "build_figure_block_from_stage06",
    "apply_layout_ordering",
    # LLM Helpers
    "extract_router_content",
    "content_to_json_dict",
    "direct_scillm_json",
    "get_usage_field",
    "call_reflow_llm",
    # Prompts
    "build_reflow_prompt",
    "build_compact_prompt",
    "build_compact_prompt_simple",
    # Data Loader
    "merge_text_blocks",
    "get_rows_cols",
    "compute_metrics_for_df",
    "merge_section_tables",
    "consolidate_data",
]

