"""Flattened pipeline package.

The legacy fail-fast pipeline has been archived. This package now exposes a
simple, stable API for extracting sections from PDFs and per-step CLIs.
"""

try:
    from .api import extract_sections, DEFAULT_RESULTS_DIR  # re-export
except ImportError:
    # If dependencies (like typer) are missing, we still want to allow importing submodules
    pass

__all__ = [
    "extract_sections",
    "DEFAULT_RESULTS_DIR",
]
