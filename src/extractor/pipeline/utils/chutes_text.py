"""High-level async text completion client with router, SDK, and curl fallback."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from scillm import acompletion as sc_acompletion

from .scillm_router import get_text_router
from .chutes_curl import chutes_curl_chat_json
from .response_utils import normalize_json_content


async def achutes_text_json(
    *,
    messages: List[Dict[str, Any]],
    temperature: float = 0.0,
    max_tokens: int = 1024,
    timeout: float = 60.0,
    tag: str = "text_call",
) -> Optional[Dict[str, Any]]:
    """Router-first → SDK → curl JSON call. Returns dict content or None.

    - Uses model_name "chutes/text" via SciLLM Router with CHUTES_TEXT_MODEL + ALT1/ALT2.
    - Falls back to scillm.acompletion (OpenAI-compatible) with Bearer.
    - Final fallback: curl; saves artifacts under scripts/artifacts/.
    """
    force_curl = os.getenv("SCILLM_FORCE_CURL", "").lower() in {"1", "true", "yes", "y"}
    # 1) Router-first (unless force-curl)
    try:
        if not force_curl:
            router = get_text_router()
            resp = await router.acompletion(
                model="chutes/text",
                messages=messages,
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            _, obj = normalize_json_content(resp)
            if isinstance(obj, dict):
                return obj
    except Exception:
        pass

    # 2) SDK (unless force-curl)
    try:
        if not force_curl:
            base = os.environ.get("SCILLM_API_BASE", "http://localhost:4010")
            key = os.environ.get("SCILLM_PROXY_KEY", "sk-dev-proxy-123")
            model = os.environ.get("CHUTES_TEXT_MODEL", "")
            if base and key and model:
                resp = await sc_acompletion(
                    model=model,
                    custom_llm_provider="openai_like",
                    api_base=base,
                    api_key=key,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
                _, obj = normalize_json_content(resp)
                if isinstance(obj, dict):
                    return obj
    except Exception:
        pass

    # 3) Curl fallback
    try:
        data, _meta = chutes_curl_chat_json(
            messages=messages,
            model=os.environ.get("CHUTES_TEXT_MODEL"),
            response_format={"type": "json_object"},
            temperature=temperature,
            max_tokens=max_tokens,
            tag=tag,
        )
        msg = (data.get("choices") or [{}])[0].get("message", {}) if isinstance(data, dict) else {}
        content = msg.get("content")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except Exception:
                content = None
        return content if isinstance(content, dict) else None
    except Exception:
        return None
