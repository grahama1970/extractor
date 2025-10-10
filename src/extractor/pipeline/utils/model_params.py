from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, List


def image_file_to_data_url(path: Path) -> str:
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
    }.get(path.suffix.lower(), "application/octet-stream")
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def build_chat_messages(
    system_text: str, user_text: str, image_data_url: str | None
) -> List[Dict[str, Any]]:
    parts: List[Dict[str, Any]] = [{"type": "text", "text": user_text}]
    if image_data_url:
        parts.append({"type": "image_url", "image_url": {"url": image_data_url}})
    return [
        {"role": "system", "content": system_text},
        {"role": "user", "content": parts},
    ]


def build_chat_extras(model_name: str) -> Dict[str, Any]:
    """Return extra kwargs for litellm.acompletion calls.

    Standardize provider knobs so JSON mode is honored across OpenAI-compatible gateways.
    - Set custom_llm_provider to "openai" by default so response_format works when routed.
    - For non-Gemini, request JSON object responses.
    - For Gemini, prefer response_mime_type JSON.
    """
    name = (model_name or "").lower()
    extras: Dict[str, Any] = {}
    # Default to OpenAI-compatible to avoid provider ambiguity and enable response_format
    extras["custom_llm_provider"] = "openai"
    if "gemini" not in name:
        extras["response_format"] = {"type": "json_object"}
    else:
        # Provider-specific GenerationConfig for Google Gemini
        extras["generation_config"] = {
            "response_mime_type": "application/json",
            # Allow generous output length for structured blocks
            "max_output_tokens": 2048,
        }
    return extras
