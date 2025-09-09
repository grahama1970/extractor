from __future__ import annotations
from typing import Any, Dict, Optional
import os

from extractor.pipeline.utils.litellm_call import litellm_call

# Tiny 1x1 transparent PNG
_TINY_PNG_B64 = (
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQAB' 
    'DQottQAAAABJRU5ErkJggg=='
)

# Simple in-process cache keyed by model
_VISION_CACHE: Dict[str, bool] = {}

def _norm_model(model: Optional[str]) -> str:
    return (model or '').strip().lower()

def get_cached_vision_support(model: str) -> Optional[bool]:
    m = _norm_model(model)
    if not m:
        return None
    if os.getenv('VISION_PREFLIGHT_ASSUME_OK', '').lower() in ('1','true','yes','y'):
        return True
    return _VISION_CACHE.get(m)

def set_cached_vision_support(model: str, supported: bool) -> None:
    m = _norm_model(model)
    if m:
        _VISION_CACHE[m] = bool(supported)

async def preflight_vision_support(model: str, timeout_sec: int = 10) -> bool:
    """Quick check if the configured model accepts an image in Chat Completions.
    Uses a 1x1 PNG data URL. Caches the result for the process lifetime.
    """
    cached = get_cached_vision_support(model)
    if cached is not None:
        return cached
    try:
        params = {
            'model': model,
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': 'preflight vision capability'},
                        {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{_TINY_PNG_B64}'}}
                    ]
                }
            ],
            'max_tokens': 1,
            'timeout': timeout_sec,
            'stream': False,
        }
        # We don't need parsed JSON, just a successful roundtrip
        _ = await litellm_call([params], wrap_json=False, concurrency=1, desc='Vision Preflight')
        set_cached_vision_support(model, True)
        return True
    except Exception:
        set_cached_vision_support(model, False)
        return False
