#!/usr/bin/env python3
"""
SciLLM Call — async batch runner using the ScillM/LiteLLM client.

Goals
- Depend only on the ScillM distribution (which currently exposes the
  `litellm` module name) — no legacy litellm_call usage.
- Provide deterministic ordering and bounded concurrency without silently
  falling back to unrelated adapters.
- Return a minimal Result object with request/response/content/exception.
"""
from __future__ import annotations

from typing import Any, Iterable, List, Dict, Optional
import asyncio

try:  # Prefer SciLLM module name
    import scillm as _backend  # type: ignore  # noqa: F401
except Exception:
    try:  # SciLLM distribution provides the 'litellm' module name
        import litellm as _backend  # type: ignore  # noqa: F401
    except Exception:
        _backend = None  # type: ignore


# Re-exported result type (duck-typed in tests)
class Result:
    """Minimal result object with request and response objects.

    Attributes
    - index: original position in the batch
    - request: the request dict we sent (model/messages/kwargs)
    - response: the raw provider response (OpenAI-like dict) if available
    - content: convenient text content extracted from response
    - exception: any exception raised during the call
    """
    def __init__(self, index: int, request: Any, response: Any = None, content: str = "", exception: Optional[Exception] = None):
        self.index = index
        self.request = request
        self.response = response
        self.content = content
        self.exception = exception


async def scillm_call(
    prompts: Iterable[Dict[str, Any]] | None = None,
    concurrency: int = 4,
    desc: str | None = None,
    session_id: str | None = None,
    export: str | None = None,
    wrap_json: bool | None = None,
    sanitize_data_urls: str | None = None,
    sanitize_truncate_chars: int | None = None,
    items: Iterable[Dict[str, Any]] | None = None,
    **kwargs: Any,
) -> List[Result]:
    """Run a batch of chat completions via ScillM/LiteLLM asynchronously.

    - Each item: {"model": str, "messages": [...], other OpenAI-compatible kwargs}
    - Bounded by `concurrency` (>=1). Order preserved.
    - No hidden fallback to legacy adapters; this uses the ScillM/LiteLLM client only.
    """
    if _backend is None:
        raise RuntimeError("ScillM/LiteLLM client not available")
    reqs = list(items or prompts or [])
    if concurrency < 1:
        concurrency = 1

    sem = asyncio.Semaphore(concurrency)
    out: List[Result] = [None] * len(reqs)  # type: ignore

    async def _one(i: int, req: Dict[str, Any]):
        model = req.get("model")
        messages = req.get("messages") or []
        # Merge pass-through kwargs from root + nested .kwargs if present
        kw = {k: v for k, v in req.items() if k not in {"model", "messages"}}
        if isinstance(req.get("kwargs"), dict):
            kw.update(req["kwargs"])  # type: ignore[index]
        try:
            async with sem:
                if hasattr(_backend, "acompletion"):
                    r = await _backend.acompletion(model=model, messages=messages, **kw)  # type: ignore
                else:
                    loop = asyncio.get_event_loop()
                    r = await loop.run_in_executor(None, lambda: _backend.completion(model=model, messages=messages, **kw))  # type: ignore
            try:
                content = r["choices"][0]["message"]["content"] if isinstance(r, dict) else getattr(r, "content", "")
            except Exception:
                content = getattr(r, "content", "") or ""
            out[i] = Result(i, request=req, response=r, content=content, exception=None)
        except Exception as ex:
            out[i] = Result(i, request=req, response=None, content="", exception=ex)

    await asyncio.gather(*[_one(i, req) for i, req in enumerate(reqs)])
    # type: ignore[return-value]
    return out  # type: ignore[return-value]
