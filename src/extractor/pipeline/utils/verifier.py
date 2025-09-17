from __future__ import annotations

import json
from typing import Any, Dict

from tenacity import retry, stop_after_attempt, wait_exponential

from extractor.pipeline.utils.litellm_call import litellm_call


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
    """Verify header using litellm_call (vision required) with strict JSON intent.

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
    results = await litellm_call(
        prompts=[{"model": model, "messages": messages}],
        wrap_json=True,
        concurrency=1,
        desc="verify header",
    )
    answer = results[0] if results else ""
    try:
        payload = json.loads(answer) if answer else {}
    except Exception:
        payload = {"error": {"type": "ParseError", "message": answer[:200]}}
    if isinstance(payload, dict) and payload.get("error"):
        err = payload["error"]
        raise RuntimeError(f"LLM error: {err.get('type')}: {err.get('message')}")
    if not isinstance(payload, dict):
        payload = {"content": payload}
    payload.setdefault("is_header", True)
    payload.setdefault("reasoning", "")
    return payload
