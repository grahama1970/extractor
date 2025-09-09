"""Flattened pipeline package.

The legacy fail-fast pipeline has been archived. This package now exposes a
simple, stable API for extracting sections from PDFs and per-step CLIs.
"""

from .api import extract_sections, DEFAULT_RESULTS_DIR  # re-export

__all__ = [
    "extract_sections",
    "DEFAULT_RESULTS_DIR",
]
