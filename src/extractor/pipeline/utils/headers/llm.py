#!/usr/bin/env python3
"""LLM verification utilities for Stage 03 (Suspicious Header Verification).

Handles VLM/text LLM calls for header verification with prompt construction.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List

from loguru import logger

from extractor.pipeline.utils.debug_utils import log_llm_call
from extractor.pipeline.utils.model_params import build_chat_extras
from extractor.pipeline.utils.prompt_loader import load_prompt
from extractor.pipeline.utils.scillm_router import get_text_router, get_vlm_router

# from extractor.pipeline.steps.scillm_preflight_validator import quick_scillm_check (Moved inside function)


# Load prompt once at module level
PROMPT = load_prompt("03_suspicious_headers")


def normalize_model_alias(model: str | None) -> str:
    """Normalize model name, stripping provider prefixes."""
    m = (model or "").strip()
    if m.lower().startswith("openai/"):
        m = m[len("openai/") :]
    return m


async def verify_header_with_llm(
    image_b64: str,
    context_text: str,
    model: str,
    *,
    item_timeout: int = 90,
) -> Dict[str, Any]:
    """Verify header using SciLLM (vision required) with strict JSON intent via Chutes.

    - Uses SciLLM Router + api_key (no manual headers)
    - Sends a single image + trimmed text context
    - Enforces response_format=json_object and stop fences for non-Gemini models
    """
    model_norm = normalize_model_alias(model)
    extras = build_chat_extras(model_norm)

    try:
        logger.info(
            f"stage03.verify_header: effective_model={model_norm} extras_keys={list(extras.keys())}"
        )
    except Exception:
        pass

    # Trim context text
    try:
        trim_chars = int(os.getenv("STAGE03_VERIFY_TRIM_CHARS", "800"))
    except Exception:
        trim_chars = 800
    if isinstance(context_text, str) and len(context_text) > trim_chars:
        context_text = context_text[:trim_chars]

    # Build message content
    text_only = os.getenv("STAGE03_TEXT_ONLY", "1").lower() in ("1", "true", "yes", "y")
    user_content: List[Any] = [{"type": "text", "text": context_text}]
    if not text_only and image_b64:
        user_content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
        )

    messages = [
        {"role": "system", "content": PROMPT["system"]},
        {"role": "user", "content": user_content},
    ]

    # Max tokens
    try:
        max_tokens = int(os.getenv("STAGE03_VERIFY_MAX_TOKENS", "256"))
    except Exception:
        max_tokens = 256

    # Timeout override
    try:
        item_timeout = int(os.getenv("SC_TIMEOUT_STAGE_03", str(item_timeout)))
    except Exception:
        pass

    # AGENTS.md compliance: validate SciLLM environment
    from extractor.pipeline.steps.scillm_preflight_validator import quick_scillm_check

    if not quick_scillm_check():
        raise RuntimeError(
            "SciLLM environment not configured; header verification requires Chutes."
        )

    get_text_router() if text_only else get_vlm_router()
    route_model = "chutes/text" if text_only else "chutes/vlm"

    # Timed SciLLM Router call
    t0 = time.monotonic()
    resp = None
    try:
        from scillm.batch import parallel_acompletions_iter

        # Prepare single request batch
        reqs = [
            {
                "model": route_model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "max_tokens": max_tokens,
                "temperature": 0,
                "timeout": item_timeout,
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
            timeout=item_timeout,
            wall_time_s=120,  # 2 min max
            tenacious=False,  # Fail fast
            response_format={"type": "json_object"},
            repair_invalid_json=True,
        ):
            if r.get("ok"):
                # Reconstruct a mock response object or just use the parsed content?
                # The downstream logic expects a 'resp' object with attributes or dict.
                # parallel_acompletions_iter yields a dict with 'parsed', 'content', 'usage'.
                # We need to adapt it to what the subsequent code expects (dict with 'model', 'usage', 'choices').

                content = r.get("content")
                r.get("parsed")

                # If parsed is available, dump it back to string for the downstream parser?
                # Or just construct the choices dict.

                # Downstream code:
                # if isinstance(resp, dict): choices = resp.get("choices") ...
                # msg = (choices[0]...).get("content") -> answer
                # payload = json.loads(answer)

                # So we can construct a compatible dict
                resp = {
                    "model": r.get("model", route_model),
                    "usage": r.get("usage"),
                    "choices": [{"message": {"content": content}}],
                }
            else:
                raise RuntimeError(f"SciLLM Error: {r.get('error')}")

        elapsed_ms = int((time.monotonic() - t0) * 1000)

    except Exception as e:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        log_llm_call(
            stage_key="03_suspicious_headers",
            task_kind="verify_header",
            route=route_model,
            model=normalize_model_alias(model),
            success=False,
            error_class=type(e).__name__,
            latency_ms=elapsed_ms,
            raw_preview=str(e),
        )
        raise

    # Log success metrics
    try:
        usage = resp.get("usage") or {}

        log_llm_call(
            stage_key="03_suspicious_headers",
            task_kind="verify_header",
            route=route_model,
            model=normalize_model_alias(model),
            success=True,
            latency_ms=elapsed_ms,
            tokens_in=usage.get("prompt_tokens"),
            tokens_out=usage.get("completion_tokens"),
        )
    except Exception:
        pass

    # Parse response
    if isinstance(resp, dict):
        choices = resp.get("choices") or [{}]
    else:
        choices = getattr(resp, "choices", [{}])
    msg = (choices or [{}])[0].get("message", {}) if isinstance(choices, list) else {}
    answer = (msg or {}).get("content", "")

    try:
        if isinstance(answer, dict):
            payload = answer
        elif isinstance(answer, str):
            payload = json.loads(answer) if answer else {}
        else:
            payload = {}
    except Exception:
        payload = {"verdict": "reject", "confidence": 0.0, "reasons": ["parse_error"]}

    if isinstance(payload, dict) and payload.get("error"):
        err = payload["error"]
        raise RuntimeError(f"LLM error: {err.get('type')}: {err.get('message')}")

    if not isinstance(payload, dict):
        payload = {"verdict": "reject", "confidence": 0.0, "reasons": ["non_dict_payload"]}

    # Normalize result
    verdict = str(payload.get("verdict", "reject")).lower()
    is_header = verdict == "accept"
    reasons = payload.get("reasons")
    if isinstance(reasons, list):
        reasons_str = "; ".join(str(r) for r in reasons if r is not None)
    else:
        reasons_str = str(payload.get("reasoning", ""))

    conf = payload.get("confidence")
    try:
        confidence = float(conf) if conf is not None else 0.0
    except Exception:
        confidence = 0.0

    return {
        "is_header": is_header,
        "reasoning": reasons_str,
        "confidence": confidence,
        "raw_payload": payload,
    }


__all__ = [
    "normalize_model_alias",
    "verify_header_with_llm",
]
