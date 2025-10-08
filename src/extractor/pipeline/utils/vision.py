from __future__ import annotations
from typing import Any, Dict, Optional
import os
import io
import base64

try:
    from PIL import Image  # type: ignore

    _HAS_PIL = True
except Exception:
    _HAS_PIL = False

import scillm
from extractor.pipeline.utils.scillm_env import build_requests

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
            except Exception:
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
                except Exception:
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
        reqs = build_requests([
            {
                "model": model,
                "messages": [{"role": "user", "content": content_parts}],
            }
        ], json_object=False, timeout=timeout_sec)
        router = scillm.Router()
        resps = await router.parallel_acompletions(reqs, max_concurrency=1)
        r0 = resps[0] if resps else None
        try:
            from loguru import logger as _logger
            if r0 and isinstance(r0, dict):
                _logger.info("vision_preflight: ok=%s", True)
        except Exception:
            pass
        # Consider an empty response as failure
        try:
            content = r0["choices"][0]["message"]["content"] if isinstance(r0, dict) else ""
        except Exception:
            content = ""
        if not content or not isinstance(content, str) or not content.strip():
            raise RuntimeError("vision_preflight_empty_response")
        set_cached_vision_support(model, True)
        return True
    except Exception:
        set_cached_vision_support(model, False)
        return False
