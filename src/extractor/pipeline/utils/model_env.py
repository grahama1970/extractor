from __future__ import annotations
import os

_VLLM_WARNED = False

def _first(*vals):
    for v in vals:
        if v and str(v).strip():
            return str(v).strip()
    return None

def get_env(*keys: str, default: str | None = None) -> str | None:
    return _first(*(os.getenv(k) for k in keys), default)

def _warn_vllm_once():
    global _VLLM_WARNED
    if _VLLM_WARNED:
        return
    if any(os.getenv(k) for k in (
        "SCILLM_SMALL_VLLM_MODEL","SCILLM_MED_VLLM_MODEL","SCILLM_LARGE_VLLM_MODEL",
        "LITELLM_SMALL_VLLM_MODEL","LITELLM_MED_VLLM_MODEL","LITELLM_LARGE_VLLM_MODEL",
    )):
        try:
            print("[Extractor][DEPRECATION] Detected *_VLLM_MODEL env; prefer *_VLM_MODEL.")
        except Exception:
            pass
        _VLLM_WARNED = True

def resolve_default(default: str | None = None) -> str:
    return get_env(
        "SCILLM_DEFAULT_MODEL",
        "LITELLM_DEFAULT_MODEL",
        "DEFAULT_LITELLM_MODEL",
        "LITELLM_MODEL",
        default=default or "openai/gpt-4o-mini",
    ) or (default or "openai/gpt-4o-mini")

def resolve_model(default: str | None = None) -> str | None:
    return resolve_default(default)

def resolve_text_tier(tier: str, default: str | None = None) -> str:
    tier = tier.lower()
    return get_env(
        f"SCILLM_{tier.upper()}_TEXT_MODEL",
        f"LITELLM_{tier.upper()}_TEXT_MODEL",
        default=default or resolve_default(default),
    ) or resolve_default(default)

def resolve_vlm_tier(tier: str, default: str | None = None) -> str:
    _warn_vllm_once()
    tier = tier.lower()
    val = get_env(
        f"SCILLM_{tier.upper()}_VLM_MODEL",
        f"SCILLM_{tier.upper()}_VLLM_MODEL",      # compat
        f"LITELLM_{tier.upper()}_VLM_MODEL",
        f"LITELLM_{tier.upper()}_VLLM_MODEL",     # compat
        "SCILLM_VISION_MODEL",                    # generic vision fallback
        default=default or resolve_default(default),
    )
    return val or resolve_default(default)

def resolve_vlm_small(default: str | None = None) -> str | None:
    return resolve_vlm_tier("small", default)

def resolve_vlm_med(default: str | None = None) -> str | None:
    return resolve_vlm_tier("med", default)

def resolve_vlm_large(default: str | None = None) -> str | None:
    return resolve_vlm_tier("large", default)

def resolve_text_small(default: str | None = None) -> str | None:
    return resolve_text_tier("small", default)

def resolve_text_med(default: str | None = None) -> str | None:
    return resolve_text_tier("med", default)

def resolve_text_large(default: str | None = None) -> str | None:
    return resolve_text_tier("large", default)
