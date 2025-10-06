from __future__ import annotations
import os

def get_env(*keys: str, default: str | None = None) -> str | None:
    for k in keys:
        v = os.getenv(k)
        if v and str(v).strip():
            return str(v).strip()
    return default

def resolve_model(default: str | None = None) -> str | None:
    # Prefer SCILLM_* then LITELLM_* then fallback/default
    return get_env(
        "SCILLM_DEFAULT_MODEL",
        "LITELLM_DEFAULT_MODEL",
        "DEFAULT_LITELLM_MODEL",
        "LITELLM_MODEL",
        default=default,
    )

def resolve_vlm_small(default: str | None = None) -> str | None:
    return get_env("SCILLM_SMALL_VLM_MODEL", "LITELLM_SMALL_VLM_MODEL", default=default)

def resolve_vlm_med(default: str | None = None) -> str | None:
    return get_env("SCILLM_MED_VLM_MODEL", "LITELLM_MED_VLM_MODEL", default=default)

def resolve_vlm_large(default: str | None = None) -> str | None:
    return get_env("SCILLM_LARGE_VLLM_MODEL", "LITELLM_LARGE_VLLM_MODEL", default=default)

def resolve_text_small(default: str | None = None) -> str | None:
    return get_env("SCILLM_SMALL_TEXT_MODEL", "LITELLM_SMALL_TEXT_MODEL", default=default)

def resolve_text_med(default: str | None = None) -> str | None:
    return get_env("SCILLM_MED_TEXT_MODEL", "LITELLM_MED_TEXT_MODEL", default=default)

def resolve_text_large(default: str | None = None) -> str | None:
    return get_env("SCILLM_LARGE_TEXT_MODEL", "LITELLM_LARGE_TEXT_MODEL", default=default)

