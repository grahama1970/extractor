from __future__ import annotations

from extractor.pipeline.utils.reliability import log_stage_error
import json
from typing import Any, Dict

from tenacity import retry, stop_after_attempt, wait_exponential

import os
from scillm import acompletion as sc_acompletion  # type: ignore


SYSTEM_PROMPT = (
    "You are an expert document analyst. Your task is to determine if a text block, "
    "which has been flagged as a 'suspicious' section header, is actually a legitimate "
    "section header or if it has been misclassified.\n\n"
    "You will be given:\n"
    "1. An image showing the text block in question, along with the text immediately above and below it for visual context.\n"
    "2. The structured text content for these three blocks, including font style information.\n\n"
    "Analyze both the visual layout (font size, boldness, spacing) and the text content. "
    "Based on your analysis, provide a JSON response with two keys: 'is_header' (boolean) and 'reasoning' (string)."
)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, max=10))
async def verify_header_with_llm(image_b64: str, context_text: str, model: str) -> Dict[str, Any]:
    """Verify header using SciLLM acompletion (vision) with strict JSON intent.

    Always sends an image; provider error will be raised to the caller.
    """
    user_content: Any = [
        {"type": "text", "text": context_text},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
    ]
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    ch_base = os.getenv("CHUTES_API_BASE")
    ch_key = os.getenv("CHUTES_API_KEY")
    resp = await sc_acompletion(
        model=model,
        api_base=ch_base,
        api_key=ch_key,
        custom_llm_provider="openai",
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0,
        timeout=int(os.getenv("VERIFIER_TIMEOUT", "30")),
        max_tokens=256,
    )
    content = (resp.get("choices") or [{}])[0].get("message", {}).get("content")
    answer = content if isinstance(content, str) else json.dumps(content or {})
    try:
        payload = json.loads(answer) if answer else {}
    except Exception as exc:
        log_stage_error("verifier.py", exc, {"context": "verifier.py"})
        raise
        payload = {"error": {"type": "ParseError", "message": answer[:200]}}
    if isinstance(payload, dict) and payload.get("error"):
        err = payload["error"]
        raise RuntimeError(f"LLM error: {err.get('type')}: {err.get('message')}")
    if not isinstance(payload, dict):
        payload = {"content": payload}
    payload.setdefault("is_header", True)
    payload.setdefault("reasoning", "")
    return payload
