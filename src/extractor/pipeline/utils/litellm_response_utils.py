from __future__ import annotations

"""
Compatibility layer for tests expecting `extractor.pipeline.utils.litellm_response_utils`.

Exports a stable surface by aliasing functions from `response_utils.py`:
- extract_content
- augment_json_with_cost
- classify_error
- format_error

Keep this as a thin facade to avoid duplicate logic.
"""

from .response_utils import (
    extract_content,
    augment_json_with_cost,
    classify_error,
    format_error,
)

__all__ = [
    "extract_content",
    "augment_json_with_cost",
    "classify_error",
    "format_error",
]

