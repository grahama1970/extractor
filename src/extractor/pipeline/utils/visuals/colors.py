#!/usr/bin/env python3
"""Color palettes and styling for Stage 09a (PDF Annotator).

Centralizes color definitions and style functions.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

# Stroke colors (0..1 RGB) chosen for readability & CVD safety.
COLORS: Dict[str, Tuple[float, float, float]] = {
    "section": (0.051, 0.580, 0.533),  # teal-600
    "section_frame": (0.051, 0.580, 0.533),
    "text_chunk": (0.392, 0.455, 0.545),  # slate-500
    "reflow_paragraph": (0.392, 0.455, 0.545),
    "reflow_list": (0.392, 0.455, 0.545),
    "reflow_heading": (0.051, 0.580, 0.533),
    "figure": (0.145, 0.388, 0.922),  # blue-600
    "reflow_figure": (0.145, 0.388, 0.922),
    "table": (0.863, 0.149, 0.149),  # red-600
    "reflow_table": (0.730, 0.100, 0.100),
    "table_merged": (0.730, 0.100, 0.100),
    "requirement": (0.851, 0.467, 0.024),  # amber-600
    "grid": (0.612, 0.639, 0.686),  # slate-400
    "columns": (0.055, 0.647, 0.655),  # teal-ish
    "header_candidate": (0.851, 0.024, 0.851),
    "table_rejected": (0.35, 0.35, 0.35),
}

# Human-friendly gutter labels
HUMAN_KIND: Dict[str, str] = {
    "section": "Section Header",
    "reflow_heading": "Section Header",
    "reflow_paragraph": "Text Block",
    "reflow_list": "Text Block",
    "text_chunk": "Text Block",
    "figure": "Figure",
    "reflow_figure": "Figure",
    "table": "Table",
    "table_merged": "Table",
    "reflow_table": "Table",
    "requirement": "Requirement",
}

# Tab colors
TAB_COLORS: Dict[str, Tuple[float, float, float]] = {
    "section": (0.82, 0.92, 0.82),
    "table": (0.95, 0.85, 0.85),
    "more": (0.9, 0.9, 0.9),
}

# Drawing constants
GUTTER_PAD = 0.0
PLAQUE_PAD_X = 0.0
PLAQUE_FONT_MIN = 5.5
PLAQUE_FILL: Optional[Tuple[float, float, float]] = None
PLAQUE_BORDER: Optional[Tuple[float, float, float]] = None
GUTTER_BORDER: Optional[Tuple[float, float, float]] = None

LABEL_MARGIN_PTS = 14.0
LABEL_MIN_FONT = 8.0
LABEL_BG = (1.0, 0.98, 0.85)
LABEL_TEXT_COLOR = (0.1, 0.1, 0.1)
TABLE_CALLOUT_BG = (0.98, 0.99, 0.92)
FIGURE_CALLOUT_BG = (0.94, 0.97, 1.0)

PREVIEW_DPI = 144
MAX_TABS_PER_PAGE = 12
TAB_GUTTER_WIDTH = 48.0
TAB_HEIGHT = 34.0
TAB_GAP = 6.0


def lighten(rgb: Tuple[float, float, float], f: float = 0.98) -> Tuple[float, float, float]:
    """Create a lighter version of a color."""
    r, g, b = rgb
    return (1 - (1 - r) * f, 1 - (1 - g) * f, 1 - (1 - b) * f)


def style_for_kind(
    kind: str,
) -> Tuple[Tuple[float, float, float], Optional[Tuple[float, float, float]], float]:
    """Get stroke, fill, and opacity for an overlay kind.

    Returns:
        (stroke_color, fill_color, opacity)
    """
    stroke = COLORS.get(kind, (0.3, 0.3, 0.3))
    # Use stroke-only overlays for core kinds
    if kind in {"figure", "table", "table_merged", "section", "requirement"}:
        return stroke, None, 0.0
    fill = lighten(stroke, 0.98)
    return stroke, fill, 0.10


def color_for_kind(kind: str) -> Tuple[float, float, float]:
    """Get the stroke color for an overlay kind."""
    return COLORS.get(kind, (0.3, 0.3, 0.3))


__all__ = [
    "COLORS",
    "HUMAN_KIND",
    "TAB_COLORS",
    "GUTTER_PAD",
    "PLAQUE_PAD_X",
    "PLAQUE_FONT_MIN",
    "PLAQUE_FILL",
    "PLAQUE_BORDER",
    "GUTTER_BORDER",
    "LABEL_MARGIN_PTS",
    "LABEL_MIN_FONT",
    "LABEL_BG",
    "LABEL_TEXT_COLOR",
    "TABLE_CALLOUT_BG",
    "FIGURE_CALLOUT_BG",
    "PREVIEW_DPI",
    "MAX_TABS_PER_PAGE",
    "TAB_GUTTER_WIDTH",
    "TAB_HEIGHT",
    "TAB_GAP",
    "lighten",
    "style_for_kind",
    "color_for_kind",
]
