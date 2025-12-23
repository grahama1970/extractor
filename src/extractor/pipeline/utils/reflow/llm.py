#!/usr/bin/env python3
"""LLM utilities for Stage 07 (Section Reflow).

Provides a centralized wrapper for Chutes text router calls with consistent
telemetry logging via log_llm_call.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from extractor.pipeline.utils.debug_utils import log_llm_call
from extractor.pipeline.utils.scillm_router import get_text_router
from extractor.pipeline.steps.scillm_preflight_validator import quick_scillm_check

async def call_reflow_llm(
    stage_key: str,
    task_kind: str,
    messages: List[Dict[str, Any]],
    max_tokens: int,
    timeout: int,
    temperature: float = 0.0,
    section_id: Optional[str] = None,
) -> Any:
    """Execute a text LLM call with telemetry logging.

    Args:
        stage_key: Pipeline stage identifier (e.g. "07_reflow_section")
        task_kind: Specific task label (e.g. "reflow_simple", "summarize")
        messages: List of message dicts
        max_tokens: Max output tokens
        timeout: Timeout in seconds
        temperature: Sampling temperature
        section_id: Optional section ID for context

    Returns:
        The raw response object/dict from the router.
    """
    if not quick_scillm_check():
        raise RuntimeError("SciLLM environment not configured; reflow requires Chutes.")

    router = get_text_router()
    model_name = "chutes/text"

    t0 = time.monotonic()
    success = False
    err_ex = None
    resp = None

    try:
        resp = await router.acompletion(
            model=model_name,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )
        success = True
    except Exception as exc:
        err_ex = exc
        raise
    finally:
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        # Extract usage and model info if successful
        tokens_in = None
        tokens_out = None
        served_model = None

        if success and resp:
            usage = getattr(resp, "usage", None)
            if not usage and isinstance(resp, dict):
                usage = resp.get("usage")
            
            if usage:
                if isinstance(usage, dict):
                    tokens_in = usage.get("prompt_tokens")
                    tokens_out = usage.get("completion_tokens")
                else:
                    tokens_in = getattr(usage, "prompt_tokens", None)
                    tokens_out = getattr(usage, "completion_tokens", None)
            
            if isinstance(resp, dict):
                served_model = resp.get("model")
            else:
                served_model = getattr(resp, "model", None)

        log_llm_call(
            stage_key=stage_key,
            task_kind=task_kind,
            route=model_name,
            model=served_model or model_name,
            success=success,
            section_id=section_id,
            error_class=type(err_ex).__name__ if err_ex else None,
            latency_ms=elapsed_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            raw_preview=str(err_ex) if err_ex else None,
        )

    return resp
