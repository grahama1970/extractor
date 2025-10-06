from __future__ import annotations
import os
from typing import Any, Dict, List


def provider_fields_for_model(model_alias: str) -> Dict[str, Any]:
    """Return provider routing fields for SciLLM given a model alias.
    - For ollama/* → provider=ollama, api_base from OLLAMA_API_BASE, no api_key.
    - Otherwise → provider=openai, api_base from CHUTES_API_BASE, api_key from CHUTES_API_KEY.
    """
    is_ollama = model_alias.startswith("ollama/")
    if is_ollama:
        return {
            "custom_llm_provider": "ollama",
            "api_base": os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434"),
            "api_key": None,
        }
    return {
        "custom_llm_provider": (os.getenv("CHUTES_PROVIDER") or "openai").strip() or "openai",
        "api_base": os.getenv("CHUTES_API_BASE", "https://llm.chutes.ai/v1"),
        "api_key": os.getenv("CHUTES_API_KEY"),
    }


def build_requests(models_messages: List[Dict[str, Any]], *, json_object: bool | None = None, timeout: int | None = None, temperature: float | None = None) -> List[Dict[str, Any]]:
    """Given a list of {model, messages}, attach provider, base/key, and extras.
    Set response_format json_object if requested; attach timeout/temperature if provided.
    """
    out: List[Dict[str, Any]] = []
    for mm in models_messages:
        model = str(mm["model"]).strip()
        req: Dict[str, Any] = {
            "model": model,
            "messages": mm["messages"],
        }
        req.update(provider_fields_for_model(model))
        if json_object:
            req["response_format"] = {"type": "json_object"}
        if timeout is not None:
            req["timeout"] = timeout
        if temperature is not None:
            req["temperature"] = temperature
        out.append(req)
    return out

