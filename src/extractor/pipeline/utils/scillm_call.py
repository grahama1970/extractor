#!/usr/bin/env python3
"""
SciLLM Call — transitional thin async batch runner.

Notes
- This is a compatibility wrapper to allow replacing imports of
  `extractor.pipeline.utils.litellm_call.litellm_call` with
  `extractor.pipeline.utils.scillm_call.scillm_call` without touching
  call sites yet.
- Internally, it forwards to the existing implementation for now. We can
  swap the internals to SciLLM Router-only once we retire litellm_call.
"""
from __future__ import annotations

from typing import Any, Iterable, List, Dict, Optional

try:
    # Prefer SciLLM import to ensure the module is present when needed
    import scillm as _scillm  # noqa: F401
except Exception:
    _scillm = None  # type: ignore


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
    concurrency: int = 1,
    desc: str | None = None,
    session_id: str | None = None,
    export: str | None = None,
    wrap_json: bool | None = None,
    sanitize_data_urls: str | None = None,
    sanitize_truncate_chars: int | None = None,
    items: Iterable[Dict[str, Any]] | None = None,
    **kwargs: Any,
) -> List[Result]:
    """Direct SciLLM Router parallel_acompletions with a conservative fallback.

    Expects each prompt like: {"model": str, "messages": [...], "kwargs": {...}}
    Returns a list of _Result with .index, .content, .request, .exception.
    """
    reqs = list(items or prompts or [])
    # Prefer Router.parallel_acompletions
    try:
        from scillm import Router  # type: ignore
        router = Router()
        # router.parallel_acompletions signature may vary; pass through our batch
        resps = await router.parallel_acompletions(reqs)
        out: List[Result] = []
        for i, r in enumerate(resps or []):
            try:
                content = r["choices"][0]["message"]["content"] if isinstance(r, dict) else getattr(r, "content", "")
            except Exception:
                content = getattr(r, "content", "") or ""
            out.append(Result(index=i, request=reqs[i], response=r, content=content, exception=None))
        return out
    except Exception as e:
        # Fallback: sequential completion to avoid breaking pipelines
        out: List[Result] = []
        try:
            import scillm as _s  # type: ignore
        except Exception:
            _s = None
        for i, req in enumerate(reqs):
            try:
                if _s is None:
                    raise RuntimeError("scillm not available")
                model = req.get("model")
                messages = req.get("messages")
                kwargs2 = req.get("kwargs") or {}
                # Prefer async if scillm exposes it; else run in thread
                if hasattr(_s, "acompletion"):
                    r = await _s.acompletion(model=model, messages=messages, **kwargs2)  # type: ignore
                else:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    r = await loop.run_in_executor(None, lambda: _s.completion(model=model, messages=messages, **kwargs2))  # type: ignore
                try:
                    content = r["choices"][0]["message"]["content"] if isinstance(r, dict) else getattr(r, "content", "")
                except Exception:
                    content = getattr(r, "content", "") or ""
                out.append(Result(i, request=req, response=r, content=content, exception=None))
            except Exception as ex:
                out.append(Result(i, request=req, response=None, content="", exception=ex))
        return out
