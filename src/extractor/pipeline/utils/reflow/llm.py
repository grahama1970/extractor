#!/usr/bin/env python3
"""LLM utilities for Stage 07 (Section Reflow).

Provides a centralized wrapper for Chutes text router calls with consistent
telemetry logging via log_llm_call.
"""

from __future__ import annotations

import time
import os
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

    get_text_router()
    model_name = "chutes/text"

    t0 = time.monotonic()
    success = False
    err_ex = None
    resp = None

    try:
        from scillm.batch import parallel_acompletions_iter

        reqs = [
            {
                "model": model_name,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "max_tokens": max_tokens,
                "temperature": temperature,
                "timeout": timeout,
                "index": 0,
            }
        ]

        api_key = os.getenv("CHUTES_API_KEY")
        api_base = os.getenv("CHUTES_API_BASE", "https://llm.chutes.ai/v1")

        async for r in parallel_acompletions_iter(
            reqs,
            api_base=api_base,
            api_key=api_key,
            custom_llm_provider="openai_like",  # Required per SCILLM_PAVED_PATH_CONTRACT
            concurrency=1,
            timeout=timeout,
            wall_time_s=180,  # 3 min max
            tenacious=False,  # Fail fast
            response_format={"type": "json_object"},
        ):
            if r.get("ok"):
                # Adapt to expected response format (dict or object)
                # The original code handled both dict and object.
                # parallel_acompletions_iter returns a dict.
                # We can just return a dict mimicking the OpenAI structure for compatibility
                # or just return the scillm result if the caller handles it.
                # Looking at usage in call_reflow_llm, it extracts 'usage' and 'model'.

                content = r.get("content")

                resp = {
                    "model": r.get("model", model_name),
                    "usage": r.get("usage"),
                    "choices": [{"message": {"content": content}}],
                    # Scillm might put parsed json in 'parsed'
                    "parsed": r.get("parsed"),
                }
                success = True
            else:
                # If checking "ok", treating as exception?
                # Original code raised exception on fail.
                raise RuntimeError(f"Reflow LLM Error: {r.get('error')}")

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
            usage = resp.get("usage")
            if usage:
                tokens_in = usage.get("prompt_tokens")
                tokens_out = usage.get("completion_tokens")
            served_model = resp.get("model")

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
