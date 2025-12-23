#!/usr/bin/env python3
"""
Pipeline Stage 9: Concurrent Section Summarizer (After Theorem Prover)

Purpose
- Generate JSON summaries for each reflowed section (2–4 sentences + 3–7 key concepts).
- Runs after theorem proving (08) and before export (10), so summaries can include proven requirements.

How it works (read before editing)
- Input: 07_reflowed.json (reflowed_sections).
- For each section: build a prompt with rolling context (previous summaries), send to SciLLM via Router.
- Strict JSON enforced (`response_format={"type":"json_object"}`) and paved-path only.
- Concurrency controlled by `max_concurrent` (default 5); respect tenant rate limits by setting
  `SCILLM_ROUTER_MAX_CONC` / `SCILLM_PAVED_MAX_CONCURRENT` or `max_concurrent` lower when needed.
- Fallback: if router returns empty content, do a direct SciLLM call (still paved-path, no manual headers).
- Output: 09_summaries.json + timings. Returns the path to the summaries JSON.

Paved-path compliance
- Uses SciLLM Router (chutes/text), no manual headers, no raw HTTP. Preflight enforced in run_pipeline.
"""

import os
import json
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from textwrap import dedent

# Third-party
from loguru import logger
from rich.console import Console
from extractor.pipeline.utils.json_utils import clean_json_string, restrict_top_level_keys
from extractor.pipeline.utils.json_mode import JSON_SYSTEM_GUARD
from tqdm import tqdm
from extractor.pipeline.utils.scillm_router import get_text_router
from extractor.pipeline.utils.reliability import log_stage_error
from extractor.pipeline.utils.model_select import get_text_model
from extractor.pipeline.utils.step_sanity import run_step_sanity
from extractor.pipeline.steps.scillm_preflight_validator import require_scillm_preflight
from extractor.pipeline.utils.prompt_loader import load_prompt
from extractor.pipeline.utils.debug_utils import log_llm_call

# Note: Avoid import-time side effects. Tests can import this module safely.

console = Console()
STEP_NAME = "09_section_summarizer"
PROMPT = load_prompt("09_section_summarizer")


def _choice_content(resp: Any) -> str:
    try:
        return resp.choices[0].message.content  # type: ignore[attr-defined]
    except Exception as exc:
        log_stage_error(STEP_NAME, exc, {'context': '09'})
        raise
        return ""


def sanity() -> int:
    return run_step_sanity(STEP_NAME)

# Monkeypatch hook for tests: provide a placeholder litellm_call that tests can override
def litellm_call(prompts, **kwargs):  # type: ignore[unused-argument]
    raise RuntimeError("litellm_call is not implemented in stage 09; tests may monkeypatch it.")


def _choice_content(resp: Any) -> Optional[str]:
    try:
        choices = getattr(resp, "choices", None)
        if not choices and isinstance(resp, dict):
            choices = resp.get("choices")
        if not choices:
            return None
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
        else:
            message = getattr(first, "message", None)
        if isinstance(message, dict):
            return message.get("content")
        return getattr(message, "content", None)
    except Exception as exc:
        log_stage_error(STEP_NAME, exc, {'context': '09'})
        raise
        return None


async def _direct_scillm_summary_call(
    messages: List[Dict[str, Any]],
    *,
    response_format: Optional[Dict[str, Any]] = None,
    timeout: int,
) -> Optional[str]:
    try:
        from scillm import acompletion as _sc_acompletion  # type: ignore
    except Exception as exc:
        log_stage_error(STEP_NAME, exc, {'context': '09'})
        raise
        return None
    try:
        resp = await _sc_acompletion(
            model=os.environ.get("CHUTES_TEXT_MODEL", ""),
            api_base=os.environ.get("CHUTES_API_BASE", ""),
            api_key=os.environ.get("CHUTES_API_KEY", ""),
            custom_llm_provider="openai_like",
            messages=messages,
            response_format=response_format or {"type": "json_object"},
            temperature=0.0,
            timeout=timeout,
        )
        log_llm_call(
            stage_key="09_summarizer",
            task_kind="direct_summary_fallback",
            route_name="chutes/text",
            model="chutes/text",
            success=True,
            raw_response=resp,
        )
    except Exception as exc:
        logger.warning("stage09.direct_scillm_retry_failed error=%s", exc)
        return None
    return _choice_content(resp)


