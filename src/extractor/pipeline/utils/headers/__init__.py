"""Headers utilities package for Stage 03.

Extracts pure utility functions from 03_suspicious_headers.py
to reduce file size and eliminate heuristic logic duplication.
"""

# Heuristics
from extractor.pipeline.utils.headers.heuristics import (
    normalize_header_text,
    font_signature,
    analyze_header_heuristics,
    is_relevant_for_stage03,
)

# LLM
from extractor.pipeline.utils.headers.llm import (
    normalize_model_alias,
    verify_header_with_llm,
)

__all__ = [
    # Heuristics
    "normalize_header_text",
    "font_signature",
    "analyze_header_heuristics",
    "is_relevant_for_stage03",
    # LLM
    "normalize_model_alias",
    "verify_header_with_llm",
]
