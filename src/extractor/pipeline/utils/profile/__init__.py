"""Profile detection utilities for Stage-00.

Splits the monolithic s00_profile_detector into focused modules:
- toc: Table of Contents extraction (embedded + text-based + HURIDOCS)
- timeout: Pipeline timeout estimation (learned + heuristic)
- sections: Section/formula/requirement detection (regex + font-based)
- tables: Table region estimation via line drawings
- classifier: Document type classifier (vision + text features)
- preset: Preset registry matching
"""

from extractor.pipeline.utils.profile.toc import (
    extract_toc,
    extract_toc_from_doc,
)
from extractor.pipeline.utils.profile.timeout import (
    estimate_timeout,
)
from extractor.pipeline.utils.profile.sections import (
    detect_formulas,
    detect_section_style,
    detect_requirements,
    estimate_section_count,
    estimate_section_count_by_font,
    estimate_sections_from_font_data,
    FORMULA_PATTERNS,
    SECTION_PATTERNS,
    SECTION_COUNT_PATTERNS,
    COMMON_HEADERS,
    REQUIREMENT_PATTERNS,
)
from extractor.pipeline.utils.profile.tables import (
    estimate_table_regions,
)
from extractor.pipeline.utils.profile.classifier import (
    extract_page_images,
    predict_with_classifier_images,
    load_classifier_lazily,
    ensure_torch,
)
from extractor.pipeline.utils.profile.preset import match_preset

__all__ = [
    "extract_toc",
    "extract_toc_from_doc",
    "estimate_timeout",
    "detect_formulas",
    "detect_section_style",
    "detect_requirements",
    "estimate_section_count",
    "estimate_section_count_by_font",
    "estimate_sections_from_font_data",
    "estimate_table_regions",
    "extract_page_images",
    "predict_with_classifier_images",
    "load_classifier_lazily",
    "ensure_torch",
    "FORMULA_PATTERNS",
    "SECTION_PATTERNS",
    "SECTION_COUNT_PATTERNS",
    "COMMON_HEADERS",
    "REQUIREMENT_PATTERNS",
    "match_preset",
]
