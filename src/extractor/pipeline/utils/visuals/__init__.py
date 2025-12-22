"""Visuals utilities package for Stage 09a.

Extracts PDF annotation functions from 09a_pdf_annotator.py.
"""

# Colors and styling
from extractor.pipeline.utils.visuals.colors import (
    COLORS,
    HUMAN_KIND,
    TAB_COLORS,
    GUTTER_PAD,
    PLAQUE_PAD_X,
    PLAQUE_FONT_MIN,
    LABEL_MARGIN_PTS,
    LABEL_MIN_FONT,
    LABEL_BG,
    LABEL_TEXT_COLOR,
    TABLE_CALLOUT_BG,
    FIGURE_CALLOUT_BG,
    MAX_TABS_PER_PAGE,
    TAB_GUTTER_WIDTH,
    TAB_HEIGHT,
    TAB_GAP,
    lighten,
    style_for_kind,
    color_for_kind,
)

# Geometry
from extractor.pipeline.utils.visuals.geometry import (
    safe_get_bbox,
    rect_from_pdf_bbox,
    rect_for_kind,
    coerce_page,
)

# Formatting
from extractor.pipeline.utils.visuals.formatting import (
    wrap_label_lines,
    format_label,
    stable_overlay_id,
    headers_preview_from_table,
    rows_preview_from_table,
    table_payload_from_obj,
)

__all__ = [
    # Colors
    "COLORS",
    "HUMAN_KIND",
    "TAB_COLORS",
    "GUTTER_PAD",
    "PLAQUE_PAD_X",
    "PLAQUE_FONT_MIN",
    "LABEL_MARGIN_PTS",
    "LABEL_MIN_FONT",
    "LABEL_BG",
    "LABEL_TEXT_COLOR",
    "TABLE_CALLOUT_BG",
    "FIGURE_CALLOUT_BG",
    "MAX_TABS_PER_PAGE",
    "TAB_GUTTER_WIDTH",
    "TAB_HEIGHT",
    "TAB_GAP",
    "lighten",
    "style_for_kind",
    "color_for_kind",
    # Geometry
    "safe_get_bbox",
    "rect_from_pdf_bbox",
    "rect_for_kind",
    "coerce_page",
    # Formatting
    "wrap_label_lines",
    "format_label",
    "stable_overlay_id",
    "headers_preview_from_table",
    "rows_preview_from_table",
    "table_payload_from_obj",
]
