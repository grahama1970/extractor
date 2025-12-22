from __future__ import annotations
from extractor.pipeline.utils.reliability import log_stage_error
from typing import Any, Dict, Optional
import os
import io
import base64

try:
    from PIL import Image  # type: ignore

    _HAS_PIL = True
except Exception as exc:
    log_stage_error('vision.py', exc, {'context': 'vision.py'})
    raise
    _HAS_PIL = False

from scillm import acompletion as sc_acompletion  # type: ignore

# Tiny 1x1 transparent PNG
_TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQAB"
    "DQottQAAAABJRU5ErkJggg=="
)

# Simple in-process cache keyed by model
_VISION_CACHE: Dict[str, bool] = {}


def _norm_model(model: Optional[str]) -> str:
    return (model or "").strip().lower()


def get_cached_vision_support(model: str) -> Optional[bool]:
    m = _norm_model(model)
    if not m:
        return None
    if os.getenv("VISION_PREFLIGHT_ASSUME_OK", "").lower() in ("1", "true", "yes", "y"):
        return True
    return _VISION_CACHE.get(m)


def set_cached_vision_support(model: str, supported: bool) -> None:
    m = _norm_model(model)
    if m:
        _VISION_CACHE[m] = bool(supported)


async def preflight_vision_support(model: str, timeout_sec: int = 10) -> bool:
    """Quick check if the configured model accepts an image in Chat Completions.
    Uses a generated PNG data URL (default 256x256 to satisfy providers like Gemini Flash).
    Caches the result for the process lifetime.
    """
    cached = get_cached_vision_support(model)
    if cached is not None:
        return cached
    try:
        # Build an inline PNG data URL by default to avoid any external fetches.
        # Some providers (e.g., Gemini Flash) reject very small images; generate
        # a square image of configurable size (default 256x256).
        use_remote = os.getenv("VISION_PREFLIGHT_USE_REMOTE", "").lower() in (
            "1",
            "true",
            "yes",
            "y",
        )
        image_part: Dict[str, Any]
        if use_remote:
            image_part = {
                "type": "image_url",
                "image_url": {"url": "https://httpbin.org/image/png"},
            }
        else:
            size = 256
            try:
                size = int(os.getenv("VISION_PREFLIGHT_SIZE", "256"))
            except Exception as exc:
                log_stage_error('vision.py', exc, {'context': 'vision.py'})
                raise
                size = 256
            if _HAS_PIL and size >= 1:
                # Generate an in-memory PNG (solid light gray) of the requested size
                try:
                    img = Image.new("RGB", (size, size), color=(224, 224, 224))
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                    image_part = {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    }
                except Exception as exc:
                    log_stage_error('vision.py', exc, {'context': 'vision.py'})
                    raise
                    image_part = {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{_TINY_PNG_B64}"},
                    }
            else:
                # Fallback to tiny PNG if PIL is unavailable
                image_part = {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{_TINY_PNG_B64}"},
                }

        # Provider flavor for content parts
        is_gemini = "gemini" in (model or "").lower()
        # Gemini expects input_text/input_image parts; others accept text/image_url
        content_parts = [
            (
                {"type": "input_text", "text": "preflight vision capability"}
                if is_gemini
                else {"type": "text", "text": "preflight vision capability"}
            ),
            (
                {"type": "input_image", "image_url": image_part["image_url"]}
                if is_gemini
                else image_part
            ),
        ]
        # We don't need parsed JSON, just a successful roundtrip
        base = os.getenv("CHUTES_API_BASE")
        key = os.getenv("CHUTES_API_KEY")
        resp = await sc_acompletion(
            model=model,
            api_base=base,
            api_key=key,
            custom_llm_provider="openai",
            messages=[{"role": "user", "content": content_parts}],
            max_tokens=32,
            timeout=timeout_sec,
        )
        content = (resp.get("choices") or [{}])[0].get("message", {}).get("content")
        if not content or (isinstance(content, str) and not content.strip()):
            raise RuntimeError("vision_preflight_empty_response")
        set_cached_vision_support(model, True)
        return True
    except Exception as exc:
        log_stage_error('vision.py', exc, {'context': 'vision.py'})
        raise
        set_cached_vision_support(model, False)
        return False
