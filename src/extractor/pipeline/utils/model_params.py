from __future__ import annotations

from extractor.pipeline.utils.reliability import log_stage_error
import base64
from pathlib import Path
import os
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
    """Return extra kwargs for SciLLM acompletion calls.

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
        # Non-Gemini: request strict JSON object responses; reduce variance
        extras["response_format"] = {"type": "json_object"}
        # Avoid provider 400s: top_p must be in (0, 1], not 0
        extras["top_p"] = 1
        extras["presence_penalty"] = 0
        extras["frequency_penalty"] = 0
    else:
        # Provider-specific GenerationConfig for Google Gemini
        extras["generation_config"] = {
            "response_mime_type": "application/json",
            # Allow generous output length for structured blocks
            "max_output_tokens": 2048,
        }
    # Optional: allow a seed via env for providers that support it
    try:
        _seed = os.getenv("STAGE_SEED")
        if _seed is not None and str(_seed).strip() != "":
            extras["seed"] = int(str(_seed).strip())
    except Exception as exc:
        log_stage_error("model_params.py", exc, {"context": "model_params.py"})
        raise
    return extras
