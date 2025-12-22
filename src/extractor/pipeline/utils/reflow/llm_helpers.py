#!/usr/bin/env python3
"""LLM helper utilities for Stage 07 Section Reflow.

Handles router response parsing, direct SciLLM calls, and JSON content normalization.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from extractor.pipeline.utils.json_utils import clean_json_string, parse_json_strict


def extract_router_content(resp: Any) -> Optional[str]:
    """Extract message content from router responses (object or dict).
    
    Handles both OpenAI-style response objects and dict responses.
    """
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
        
        if message is None:
            return None
        
        if isinstance(message, dict):
            return message.get("content")
        
        content = getattr(message, "content", None)
        if content is None and hasattr(message, "get"):
            try:
                content = message.get("content")
            except Exception:
                content = None
        
        return content
    except Exception:
        return None


def content_to_json_dict(content: Any) -> dict[str, Any]:
    """Normalize JSON content that may be a dict (already parsed) or a string.

    - If content is dict → return as-is
    - If content is str → try strict parse, then repair via clean_json_string
    - Else → raise ValueError
    """
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        if not content.strip():
            raise ValueError("empty content string")
        try:
            return parse_json_strict(content)
        except Exception:
            # Fall back to repair
            return clean_json_string(content, return_dict=True)
    raise ValueError(f"unsupported content type: {type(content)}")


async def direct_scillm_json(
    messages: List[Dict[str, Any]],
    *,
    response_format: Dict[str, Any] | None = None,
    max_tokens: int = 2048,
    timeout: int = 60,
) -> Optional[str]:
    """Call scillm.acompletion directly as a last-resort JSON fetch.
    
    Uses environment variables for model configuration:
    - CHUTES_TEXT_MODEL
    - CHUTES_API_BASE
    - CHUTES_API_KEY
    """
    try:
        from scillm import acompletion as _sc_acompletion  # type: ignore
    except ImportError:
        return None
    
    try:
        resp = await _sc_acompletion(
            model=os.environ.get("CHUTES_TEXT_MODEL", ""),
            api_base=os.environ.get("CHUTES_API_BASE", ""),
            api_key=os.environ.get("CHUTES_API_KEY", ""),
            custom_llm_provider="openai_like",
            messages=messages,
            response_format=response_format or {"type": "json_object"},
            temperature=0,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        return extract_router_content(resp)
    except Exception:
        return None


def get_usage_field(usage: Any, key: str) -> Any:
    """Safely extract a field from LLM usage object (dict or object)."""
    try:
        if isinstance(usage, dict):
            return usage.get(key)
        return getattr(usage, key, None)
    except Exception:
        return None


__all__ = [
    "extract_router_content",
    "content_to_json_dict",
    "direct_scillm_json",
    "get_usage_field",
]
