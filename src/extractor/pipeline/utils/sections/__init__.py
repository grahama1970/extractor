"""Sections utilities package for Stage 04.

Extracts section building functions from 04_section_builder.py.
Matches API contract from section_builder_utils_local (sbul).
"""

# Parsing
from extractor.pipeline.utils.sections.parsing import (
    SECTION_NUMBER_PATTERNS,
    roman_to_int,
    normalize_section_number,
    coerce_depth,
    derive_parent_number,
    analyze_section_numbering,
    derive_section_depth,
    extract_section_title,
    clean_section_title,
    detect_header_level,
    looks_like_header_text,
)

__all__ = [
    "SECTION_NUMBER_PATTERNS",
    "roman_to_int",
    "normalize_section_number",
    "coerce_depth",
    "derive_parent_number",
    "analyze_section_numbering",
    "derive_section_depth",
    "extract_section_title",
    "clean_section_title",
    "detect_header_level",
    "looks_like_header_text",
]
