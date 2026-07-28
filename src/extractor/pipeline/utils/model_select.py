#!/usr/bin/env python3
"""Canonical model selection from environment variables for VLM and text stages."""
from __future__ import annotations

import os


class ModelSelectionError(RuntimeError):
    """Handle model selection errors during runtime."""
    pass


def _get_env(name: str) -> str:
    """Fetch environment variable or raise if missing or empty."""
    v = (os.getenv(name) or "").strip()
    if not v:
        raise ModelSelectionError(f"Required env {name} is not set or empty")
    return v


def get_vlm_model() -> str:
    """Return the single, canonical VLM model for all stages.

    Policy: Only CHUTES_VLM_MODEL is allowed. No tiered fallbacks.
    """
    return _get_env("CHUTES_VLM_MODEL")


def get_text_model() -> str:
    """Return the single, canonical Text model for all stages.

    Policy: Only CHUTES_TEXT_MODEL is allowed. No tiered fallbacks.
    """
    return _get_env("CHUTES_TEXT_MODEL")
