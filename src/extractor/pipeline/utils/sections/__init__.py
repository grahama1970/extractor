"""Sections utilities package for Stage 04.

Extracts section building functions from 04_section_builder.py.
"""

# Parsing
from extractor.pipeline.utils.sections.parsing import (
    SECTION_NUMBER_PATTERNS,
    roman_to_int,
    analyze_section_numbering,
    derive_section_depth,
    extract_section_title,
    clean_section_title,
    detect_header_level,
    looks_like_header_text,
    normalize_section_number,
    derive_parent_number,
)

__all__ = [
    "SECTION_NUMBER_PATTERNS",
    "roman_to_int",
    "analyze_section_numbering",
    "derive_section_depth",
    "extract_section_title",
    "clean_section_title",
    "detect_header_level",
    "looks_like_header_text",
    "normalize_section_number",
    "derive_parent_number",
]
