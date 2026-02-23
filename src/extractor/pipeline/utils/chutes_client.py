#!/usr/bin/env python3
"""
Deprecated shim. Use `scillm.acompletion` with `api_key=` and
`scillm.paved` helpers instead of raw HTTP.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


class ChutesAuthError(RuntimeError):  # backward-compat for imports
    pass


def _headers(*args, **kwargs) -> Dict[str, str]:  # deprecated
    return {"Accept": "application/json", "Content-Type": "application/json"}


def chat_completion(
    *,
    api_base: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, Any]],
    response_format: Optional[Dict[str, Any]] = None,
    stop: Optional[List[str]] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Paved call via SciLLM; returns OpenAI-shaped dict."""
    from scillm import completion  # type: ignore

    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "api_base": api_base,
        "api_key": api_key,
        "custom_llm_provider": "openai_like",
        "timeout": timeout,
    }
    if response_format is not None:
        payload["response_format"] = response_format
    if stop is not None:
        payload["stop"] = stop
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if temperature is not None:
        payload["temperature"] = temperature
    return completion(**payload)
