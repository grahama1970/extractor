from __future__ import annotations

"""
Compatibility shims for legacy imports in tests that referenced
`extractor.pipeline.utils.litellm_image_utils`.

This module re-exports helpers from `image_helpers.py` and keeps the
existing function names used by tests:
- extract_images
- compress_image_cached
- fetch_remote_image_cached

Do not add new logic here; keep a thin alias to avoid divergence.
"""

import httpx  # re-exported for tests that monkeypatch httpx.get

from .image_helpers import (
    extract_images,
    compress_image_cached,
    fetch_remote_image_cached,
)

__all__ = [
    "extract_images",
    "compress_image_cached",
    "fetch_remote_image_cached",
    "httpx",
]
