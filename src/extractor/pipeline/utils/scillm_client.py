"""LLM adapter wrapper with schema hinting for SciLLM/Chutes completions."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional


def _get_adapter(logs_root: Optional[Path] = None):
    """Defer-import LLMAdapter to avoid hard dependency at module import time.
    Returns an adapter instance or raises ImportError when unavailable.
    """
    try:  # prefer local path when executed inside repo
        from src.llm_adapter.adapter import LLMAdapter  # type: ignore

        return LLMAdapter(logs_root=logs_root)
    except Exception:
        try:
            from llm_adapter.adapter import LLMAdapter  # type: ignore

            return LLMAdapter(logs_root=logs_root)
        except Exception as e:
            raise ImportError(
                f"LLMAdapter unavailable: {e}. Ensure scillm/adapter deps are installed."
            )


def apply_schema_hint(model: str, user_text: str) -> str:
    """
    Centralized, provider-aware schema hinting used by Step 07.

    - For Gemini, append a compact keys hint (Gemini often honors a brief inline spec).
    - For non‑Gemini (e.g., Qwen‑VL), optionally include a minimal top-level skeleton
      when STAGE07_FORCE_SCHEMA_HINT=1 (default on in our profile).
    """
    name = (model or "").lower()
    if "gemini" in name:
        hint = (
            "\nKeys: reflowed_json(object), ocr_corrections(object), "
            "improvements_made(string), summary(string)."
        )
        return f"{user_text}{hint}"
    # Non‑Gemini path (Qwen‑VL): guarded by env toggle
    if os.getenv("STAGE07_FORCE_SCHEMA_HINT", "1").lower() in ("1", "true", "yes", "y"):
        hint = (
            "\nTop-level object MUST be exactly: {"
            '"reflowed_json": object, "ocr_corrections": object, '
            '"improvements_made": string, "summary": string }. '
            'Inside reflowed_json: { "title": string, "blocks": array }. '
            "Each block is one of: paragraph/list/table/figure. "
            "Do not add extra top-level keys."
        )
        return f"{user_text}{hint}"
    return user_text


async def reflow_section(
    *,
    model: str,
    messages: List[Dict[str, Any]],
    results_base_dir: Optional[Path] = None,
    prompt_version: Optional[str] = None,
    doc_id: str = "doc",
    section_id: str = "section",
    request_id: Optional[str] = None,
    timeout: int = 60,
):
    """
    Async wrapper over the shared LLMAdapter for Step 07. Returns an adapter result
    with attributes: reflowed_json, ocr_corrections, improvements_made, summary.
    """
    logs_root = None
    if results_base_dir is not None:
        logs_root = Path(results_base_dir) / "07_reflow_section" / "logs"
    adapter = _get_adapter(logs_root)
    pv = prompt_version or os.getenv("STAGE07_PROMPT_VERSION", "reflow@0.1.0")
    rid = request_id or f"section_{section_id}"
    return await adapter.reflow_section(
        model=model,
        messages=messages,
        prompt_version=pv,
        doc_id=doc_id,
        section_id=section_id,
        request_id=rid,
        timeout=timeout,
    )


async def verify_header(
    *,
    model: str,
    messages: List[Dict[str, Any]],
    timeout: int = 90,
):
    """
    Async wrapper over the shared LLMAdapter for Stage 03 suspicious header verification.
    Returns an object with: verdict ("accept"|"reject"), reasons (List[str]).
    """
    adapter = _get_adapter(None)
    pv = os.getenv("STAGE03_PROMPT_VERSION", "header@0.1.0")
    return await adapter.verify_header(
        model=model,
        messages=messages,
        prompt_version=pv,
        doc_id="doc",
        section_id="hdr",
        request_id=f"hdr_{os.getenv('LITELLM_SESSION_ID') or 'run'}",
        timeout=timeout,
    )
