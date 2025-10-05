#!/usr/bin/env python3
"""
LiteLLM Call — thin async batch runner with minimal multimodal prep, returning structured results.

WHAT IT DOES
- Parses prompts, auto-detects images (URLs/local), compresses/fetches, and builds vision message parts.
- Groups prompts per model and runs them concurrently via LiteLLM Router (retries/semaphores).
- RETURNS: one structured object per input with BOTH the original request and the response (or exception),
  plus a human-ready `content` string (already formatted).

WHAT IT DOESN’T DO
- Doesn’t force JSON mode/system prompts/schemas/tools—pass them yourself if needed.
- Doesn’t transform tool calls; forwards as-is per request.
- Doesn’t implement custom retry logic; relies on Router.

KEY CHOICES
- Single, predictable execution path (no experimental helper branches).
- Bounded client-side concurrency to avoid request stampedes (aligned with Router cap).
- One environment source of truth for the default model: `LITELLM_DEFAULT_MODEL` in .env (fail fast if absent).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any as _Any, Dict, List, Optional, Tuple

import litellm as _litellm
from dotenv import find_dotenv, load_dotenv
from loguru import logger
from tqdm.asyncio import tqdm
from litellm import Router
_HAVE_PARALLEL_HELPERS = True  # for tests that monkeypatch this flag

# Required project utilities — fail fast if missing
from extractor.pipeline.utils.litellm_image_utils import (
    IMAGE_EXT as _IMAGE_EXT,
    compress_image,
    fetch_remote_image,
)
from extractor.pipeline.utils.litellm_response_utils import (
    assemble_stream_text,
    format_answer_with_logging,
)
from extractor.pipeline.utils.response_utils import to_messages_and_model
from extractor.pipeline.utils.log_utils import sanitize_messages_for_return

# Optional cache initializer — no-op if unavailable
try:
    from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache  # type: ignore
except ImportError:  # pragma: no cover
    initialize_litellm_cache = lambda: None  # noqa: E731


# -----------------------------------------------------------------------------
# Logging & environment
# -----------------------------------------------------------------------------
logger.remove()
_log_level = "DEBUG" if os.getenv("LITELLM_DEBUG", "").lower() in {"1","true","yes","y"} else "WARNING"
logger.add(sys.stderr, level=_log_level)

# Best-effort .env loading; no exceptions
_ = load_dotenv(find_dotenv(usecwd=True) or None)

# Bridge CHUTES_* to OPENAI_* so openai/<org>/<model> routes to Chutes automatically
if (os.getenv("CHUTES_API_BASE") and os.getenv("CHUTES_API_KEY")):
    os.environ.setdefault("OPENAI_BASE_URL", os.getenv("CHUTES_API_BASE", "https://llm.chutes.ai/v1"))
    os.environ.setdefault("OPENAI_API_KEY", os.getenv("CHUTES_API_KEY"))


DEFAULT_MODEL = (
    os.getenv("LITELLM_DEFAULT_MODEL")
    or os.getenv("DEFAULT_LITELLM_MODEL")
    or os.getenv("LITELLM_MODEL")
    or os.getenv("OLLAMA_DEFAULT_MODEL", "ollama/gemma3:12b")
)
MODEL = DEFAULT_MODEL  # compatibility alias expected by tests

# Warm-start metrics config (opt-in)
ENABLE_WARM_START_METRICS = os.getenv("ENABLE_WARM_START_METRICS", "0").lower() in {"1", "true", "yes"}
WARM_FIRST_N = int(os.getenv("WARM_START_FIRST_N", "10"))
WARM_METRICS_PATH = os.getenv("WARM_START_METRICS_PATH", "data/results/pipeline/metrics/warm_start_metrics.json")
_warm_latencies: dict[str, list[float]] = {}

# Drop unsupported provider params unless explicitly disabled
_litellm.drop_params = os.getenv("LITELLM_DROP_PARAMS", "true").lower() in {"1", "true", "yes", "y"}
# Optional: enable verbose LiteLLM debug
if os.getenv("LITELLM_DEBUG", "").lower() in {"1","true","yes","y"}:
    try:
        setattr(_litellm, "logging", True)
        setattr(_litellm, "debug", True)
    except Exception:
        pass
initialize_litellm_cache()

# Other env/defaults
IMAGE_EXT = _IMAGE_EXT
SHOW_PROGRESS = os.getenv("LITELLM_NO_PROGRESS", "").lower() not in {"1", "true", "yes"}
DEFAULT_NUM_RETRIES = int(os.getenv("LITELLM_NUM_RETRIES", "3"))
_DEFAULT_MAX_PARALLEL_STR = os.getenv("LITELLM_MAX_PARALLEL")
DEFAULT_MAX_PARALLEL: Optional[int] = (
    int(_DEFAULT_MAX_PARALLEL_STR)
    if _DEFAULT_MAX_PARALLEL_STR and _DEFAULT_MAX_PARALLEL_STR.isdigit()
    else None
)
DEFAULT_ATTACH_SESSION = os.getenv("LITELLM_ATTACH_SESSION", "true").lower() in {"1", "true", "yes", "y"}
IMAGE_CACHE_DIR = os.getenv("LITELLM_IMAGE_CACHE_DIR") or None


# -----------------------------------------------------------------------------
# Structured request/response types
# -----------------------------------------------------------------------------
@dataclass
class CallRequest:
    model: str
    messages: List[Dict[str, _Any]]
    kwargs: Optional[Dict[str, _Any]] = None  # extra params for Router.acompletion


@dataclass
class CallResult:
    index: int
    request: CallRequest
    response: Optional[_Any] = None
    exception: Optional[BaseException] = None
    # Convenience: human-ready string, already formatted by format_answer_with_logging or stream assembly
    content: Optional[str] = None


# -----------------------------------------------------------------------------
# Provider-specific sanitization
# -----------------------------------------------------------------------------
def _sanitize_kwargs_for_provider(model: str, kwargs: Dict[str, _Any]) -> Dict[str, _Any]:
    """Provider-agnostic defaults for determinism; provider cleanup still done by litellm."""
    kwargs = dict(kwargs or {})
    kwargs.setdefault("temperature", 0)
    kwargs.setdefault("top_p", 1)
    return kwargs


# -----------------------------------------------------------------------------
# Prompt preprocessing => messages
# -----------------------------------------------------------------------------
def _to_messages_and_model(
    item: _Any,
    default_model: str,
    *,
    response_format: Optional[str] = None,
    request_timeout: Optional[float] = None,
    image_cache_dir: Optional[str] = None,
) -> Tuple[str, List[Dict[str, _Any]], Dict[str, _Any]]:
    """Delegate to response_utils.to_messages_and_model (URL conversion happens later)."""
    return to_messages_and_model(
        item,
        default_model,
        response_format=response_format,
        request_timeout=request_timeout,
        image_cache_dir=image_cache_dir,
    )

async def _prepare_messages_image_urls(
    messages: list[dict[str, object]], *, image_cache_dir: str | None
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    import asyncio as _asyncio
    for msg in messages:
        if not isinstance(msg, dict):
            out.append(msg)
            continue
        role = msg.get("role")
        content = msg.get("content")
        if not isinstance(content, list):
            out.append(msg)
            continue
        new_parts: list[dict[str, object]] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "image_url":
                img = dict(part.get("image_url") or {})
                url = img.get("url")
                try:
                    if isinstance(url, str):
                        if url.startswith("data:"):
                            new_url = url
                        elif url.startswith("http"):
                            new_url = await _asyncio.to_thread(fetch_remote_image, url, cache_dir=image_cache_dir)
                        else:
                            new_url = await _asyncio.to_thread(compress_image, url, cache_dir=image_cache_dir)
                        if new_url:
                            img["url"] = new_url
                            new_parts.append({"type": "image_url", "image_url": img})
                    else:
                        new_parts.append(part)
                except Exception:
                    continue
            else:
                new_parts.append(part)
        out.append({"role": role, "content": new_parts})
    return out


# -----------------------------------------------------------------------------
# Router shutdown helper (prevents lingering background tasks keeping the loop alive)
# -----------------------------------------------------------------------------
async def _shutdown_router(router: Router) -> None:
    """
    Best-effort shutdown for Router and its internal components.
    Keeps compatibility across LiteLLM versions and avoids orphaned background work.
    """
    try:
        # Prefer async aclose() if present
        aclose = getattr(router, "aclose", None)
        if callable(aclose):
            await aclose()  # type: ignore[func-returns-value]
            return
        # Fallback: sync close()
        close = getattr(router, "close", None)
        if callable(close):
            close()  # type: ignore[func-returns-value]
    except Exception:
        pass

    async def _stop_component(obj: object) -> None:
        if not obj:
            return
        for name in ("shutdown", "stop", "close", "join", "flush", "aclose"):
            fn = getattr(obj, name, None)
            if not callable(fn):
                continue
            try:
                result = fn()
                if asyncio.iscoroutine(result):
                    try:
                        await result
                    except Exception:
                        pass
            except TypeError:
                # Some close() accept timeouts; try a benign 0
                try:
                    result = fn(0)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    pass
            except Exception:
                pass

    # Try to stop known components if exposed
    for attr in ("service_logger_obj", "scheduler"):
        try:
            await _stop_component(getattr(router, attr, None))
        except Exception:
            pass

    # Clear global callbacks that could spawn new threads
    try:
        _litellm.callbacks = []
        _litellm.success_callback = []
        _litellm.failure_callback = []
        _litellm.input_callback = []
        _litellm.service_callback = []
    except Exception:
        pass


# -----------------------------------------------------------------------------
# Core API — returns structured CallResult[] (request + response/exception + content)
# -----------------------------------------------------------------------------
async def litellm_call(
    prompts: List[_Any],
    *,
    default_model: Optional[str] = None,
    wrap_json: bool = False,
    desc: Optional[str] = None,
    session_id: Optional[str] = None,
    attach_session_to_provider: Optional[bool] = None,
    num_retries: Optional[int] = None,
    default_max_parallel_requests: Optional[int] = None,
    concurrency: Optional[int] = None,
    response_format: Optional[str] = None,
    request_timeout: Optional[float] = None,
    stream: bool = False,
    models: Optional[List[str]] = None,
    image_cache_dir: Optional[str] = None,
    show_progress: Optional[bool] = None,
    # NEW: how to sanitize base64 data-URIs in the returned request.messages of CallResult
    sanitize_data_urls: str = "redact",   # one of: "redact" (default), "hash", "truncate", "none"
    sanitize_truncate_chars: int = 48,    # used when sanitize_data_urls == "truncate"
    export: str = "content",  # 'content' (default) or 'results'
) -> List[str] | List[CallResult]:
    """
    Run prompts concurrently with automatic image support.

    RETURNS:
      A list of CallResult with:
        - .index (original input index)
        - .request (CallRequest: model/messages/kwargs)  [messages may be sanitized per `sanitize_data_urls`]
        - .response OR .exception
        - .content: a human-ready string produced by response formatting/stream assembly

    Sanitization modes (for image data-URIs in returned CallResult.request.messages):
      - "redact"  (default): replace with 'data:<mime>;base64,<redacted bytes≈N sha256=...>'
      - "hash":             replace with '<data-url sha256=... bytes≈N>'
      - "truncate":         keep head/tail of base64 with '... (bytes≈N, sha256=...)'
      - "none":             keep the original base64 (not recommended for logs)
    """
    # --- local helpers --------------------------------------------------------
    import hashlib

    def _sanitize_data_url(url: str) -> str:
        """Sanitize a data:*;base64,<blob> URL per sanitize_data_urls mode."""
        try:
            if not (isinstance(url, str) and url.startswith("data:")):
                return url
            if ";base64," not in url:
                return url  # only sanitize base64 payloads
            header, b64 = url.split(";base64,", 1)
            mime = header[5:] if header.startswith("data:") else header
            total_bytes = int(len(b64) * 3 / 4)  # rough decoded length
            sha = hashlib.sha256(b64.encode("utf-8", "ignore")).hexdigest()

            mode = (sanitize_data_urls or "redact").lower()
            if mode == "none":
                return url
            if mode == "hash":
                return f"<data-url sha256={sha} bytes≈{total_bytes}>"
            if mode == "truncate":
                n = max(0, int(sanitize_truncate_chars))
                head = b64[:n]
                tail = b64[-n:] if n > 0 else ""
                return f"data:{mime};base64,{head}...{tail}  (bytes≈{total_bytes}, sha256={sha})"
            # default = redact
            return f"data:{mime};base64,<redacted bytes≈{total_bytes} sha256={sha}>"
        except Exception:
            # On any parsing issue, fail closed by redacting entirely
            return "<data-url redacted>"

    def _sanitize_messages_for_return(messages: List[Dict[str, _Any]]) -> List[Dict[str, _Any]]:
        return sanitize_messages_for_return(messages, sanitize_data_urls, sanitize_truncate_chars)

    # Normalize input
    if isinstance(prompts, (str, dict)):
        prompts = [prompts]

    base_model = default_model or DEFAULT_MODEL
    if attach_session_to_provider is None:
        attach_session_to_provider = DEFAULT_ATTACH_SESSION

    # Router settings
    num_retries = DEFAULT_NUM_RETRIES if num_retries is None else num_retries
    if concurrency is not None and default_max_parallel_requests is None:
        default_max_parallel_requests = concurrency
    default_max_parallel_requests = (
        DEFAULT_MAX_PARALLEL if default_max_parallel_requests is None else default_max_parallel_requests
    )
    image_cache_dir = image_cache_dir if image_cache_dir is not None else IMAGE_CACHE_DIR

    # Fan-out one prompt → many models
    if models:
        expanded: List[_Any] = []
        for item in prompts:
            for m in models:
                if isinstance(item, dict):
                    it = dict(item)
                    it["model"] = m
                else:
                    it = {"text": str(item), "model": m}
                expanded.append(it)
        prompts = expanded

    # Preprocess
    processed: List[Tuple[int, str, List[Dict[str, _Any]], Dict[str, _Any]]] = []
    for idx, item in enumerate(prompts):
        model, messages, extra_kwargs = _to_messages_and_model(
            item,
            base_model,
            response_format=response_format,
            request_timeout=request_timeout,
            image_cache_dir=image_cache_dir,
        )
        processed.append((idx, model, messages, extra_kwargs))

    # Group batchables vs individuals
    batches: Dict[str, List[Tuple[int, List[Dict[str, _Any]]]]] = {}
    individuals: List[Tuple[int, str, List[Dict[str, _Any]], Dict[str, _Any]]] = []
    for idx, model, messages, extra_kwargs in processed:
        if extra_kwargs:
            individuals.append((idx, model, messages, extra_kwargs))
        else:
            batches.setdefault(model, []).append((idx, messages))

    unique_models = sorted({m for _, m, _, _ in processed})

    def _router_entry(m: str) -> dict:
        params: dict = {"model": m}
        # Route Gemini to Google provider explicitly when possible (to honor JSON structured outputs)
        if m.startswith("gemini/"):
            key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if key:
                params.update({"api_key": key, "provider": "gemini"})
        elif (
            m.startswith("openai/chutes/")
            or m.startswith("openai/chutesai/")
            or m.startswith("openai/zai-org/")
            or m.startswith("openai/deepseek-ai/")
            or m.startswith("openai/zhipu-ai/")
            or m.startswith("openai/mistralai/")
            or m.startswith("openai/Qwen/")
        ):
            key = os.getenv("CHUTES_API_KEY") or os.getenv("CHUTES_KEY")
            base = os.getenv("CHUTES_API_BASE", "https://llm.chutes.ai/v1")
            provider = (os.getenv("CHUTES_PROVIDER") or "openai").strip() or "openai"
            actual_model = os.getenv("CHUTES_REMOTE_MODEL")
            if not actual_model:
                parts = m.split("/", 2)
                # Prefer vendor/name pair for Chutes aggregator
                if len(parts) > 2:
                    vendor = parts[1]
                    name = parts[2]
                    actual_model = f"{vendor}/{name}"
                else:
                    actual_model = m
            params.update(
                {
                    "api_key": key,
                    "api_base": base,
                    "custom_llm_provider": provider,
                    "model": actual_model,
                }
            )
            if not key:
                logger.warning("CHUTES_API_KEY not set; chutes provider calls will fail")
        elif m.startswith("chutes/"):
            key = os.getenv("CHUTES_API_KEY") or os.getenv("CHUTES_KEY")
            base = os.getenv("CHUTES_API_BASE", "https://llm.chutes.ai/v1")
            provider = (os.getenv("CHUTES_PROVIDER") or "openai").strip() or "openai"
            actual_model = os.getenv("CHUTES_REMOTE_MODEL")
            if not actual_model:
                actual_model = m.split("/", 1)[1] if "/" in m else m
            params.update(
                {
                    "api_key": key,
                    "api_base": base,
                    "custom_llm_provider": provider,
                    "model": actual_model,
                }
            )
            if not key:
                logger.warning("CHUTES_API_KEY not set; chutes provider calls will fail")
        entry = {"model_name": m, "litellm_params": params}
        try:
            # Provide minimal model_info to satisfy Router health checks
            entry["model_info"] = {"id": params.get("model", m), "mode": "chat"}
        except Exception:
            pass
        return entry

    _sanitize_litellm_callbacks()
    # Router-level timeout (caps overall call, including retries)
    # Keep Router timeout bounded to avoid perceived "hangs"
    router_timeout = request_timeout if request_timeout is not None else (
        float(os.getenv("LITELLM_ROUTER_TIMEOUT", "45"))
    )
    retry_after_param = float(os.getenv("LITELLM_RETRY_AFTER", "0")) or None

    router = Router(
        model_list=[_router_entry(m) for m in unique_models],
        num_retries=num_retries,
        default_max_parallel_requests=default_max_parallel_requests,
        timeout=router_timeout,
        retry_after=retry_after_param,
    )
    _sanitize_litellm_callbacks()

    try:
        # Streaming fast-path
        if stream and len(processed) == 1 and not individuals and len(batches) == 1:
            model = unique_models[0]
            idx0, msgs0 = next(iter(batches[model]))
            kwargs: Dict[str, _Any] = {}
            if attach_session_to_provider and session_id:
                kwargs["user"] = session_id
            if request_timeout is not None:
                kwargs["timeout"] = request_timeout
            try:
                prepared = await _prepare_messages_image_urls(msgs0, image_cache_dir=image_cache_dir)
                resp_stream = await router.acompletion(model=model, messages=prepared, stream=True, **kwargs)
                content = await assemble_stream_text(resp_stream)
            except TypeError:
                prepared = await _prepare_messages_image_urls(msgs0, image_cache_dir=image_cache_dir)
                resp = await router.acompletion(model=model, messages=prepared, **kwargs)
                content = format_answer_with_logging(idx0, resp, wrap_json, prompts[idx0], logger)
            if export == "results":
                req = CallRequest(model=model, messages=_sanitize_messages_for_return(msgs0), kwargs=kwargs or None)
                return [CallResult(index=idx0, request=req, response=None, exception=None, content=content)]
            return [content]

        # Bounded concurrency over acompletion
        limit_client = concurrency or (DEFAULT_MAX_PARALLEL or 8)
        sem = asyncio.Semaphore(limit_client)

        async def _call_one(
            idx: int, model: str, messages: List[Dict[str, _Any]], extra: Dict[str, _Any]
        ) -> CallResult:
            kwargs = dict(extra)
            if attach_session_to_provider and session_id and "user" not in kwargs:
                kwargs["user"] = session_id
            if request_timeout is not None and "timeout" not in kwargs:
                kwargs["timeout"] = request_timeout
            kwargs = _sanitize_kwargs_for_provider(model, kwargs)
            prepared = await _prepare_messages_image_urls(messages, image_cache_dir=image_cache_dir)
            req = CallRequest(model=model, messages=_sanitize_messages_for_return(prepared), kwargs=kwargs or None)
            async with sem:
                tried_fallback = False
                attempt_model = model
                attempts = 0
                while True:
                    try:
                        t0 = time.perf_counter() if 'time' in globals() else None
                        resp = await router.acompletion(model=attempt_model, messages=prepared, **kwargs)
                        if t0 is not None and os.getenv("ENABLE_WARM_START_METRICS", "0") in ("1","true","yes"):
                            dt = (time.perf_counter() - t0) * 1000.0
                            try:
                                import statistics as _stats  # noqa
                            except Exception:
                                pass
                        content = format_answer_with_logging(idx, resp, wrap_json, prompts[idx], logger)
                        return CallResult(idx, req, resp, None, content)
                    except BaseException as e:
                        etype = type(e).__name__
                        status_str = getattr(getattr(e, "response", None), "status_code", None)
                        attempts += 1
                        # 429 handling with Retry-After
                        if status_str == 429:
                            headers = getattr(getattr(e, "response", None), "headers", {}) or {}
                            ra = headers.get("Retry-After") if isinstance(headers, dict) else None
                            try:
                                delay = float(ra) if ra else (1.0 if attempts == 1 else 2.0)
                            except Exception:
                                delay = 1.0 if attempts == 1 else 2.0
                            await asyncio.sleep(delay)
                            if attempts <= (num_retries or 0):
                                continue
                            return CallResult(idx, req, None, e, None)
                        fast_fail = (
                            "AuthenticationError" in etype
                            or "NotFound" in etype
                            or status_str in (401, 403, 404)
                        )
                        if fast_fail and not tried_fallback:
                            fb = os.getenv("LITELLM_LARGE_VLLM_MODEL") or os.getenv("LITELLM_LARGE_VLM_MODEL") or "openai/deepseek-ai/DeepSeek-V3-0324"
                            if fb and fb != attempt_model:
                                logger.warning(f"Model '{attempt_model}' failed with {etype}; retrying once with fallback '{fb}'.")
                                attempt_model = fb
                                tried_fallback = True
                                # attempt to register fallback if not in router already
                                try:
                                    if all(fb != entry.get("model_name") for entry in getattr(router, "model_list", [])):
                                        router.model_list.append(_router_entry(fb))
                                except Exception:
                                    pass
                                continue
                        logger.exception("litellm_call task failed (idx=%s, model=%s fast_fail=%s)", idx, attempt_model, fast_fail)
                        # Generic 5xx: limited retries with backoff
                        try:
                            if str(status_str).startswith("5") and attempts <= (num_retries or 0):
                                await asyncio.sleep(1.0 * attempts)
                                continue
                        except Exception:
                            pass
                        content = format_answer_with_logging(idx, e, wrap_json, prompts[idx], logger)
                        return CallResult(idx, req, None, e, content)

        tasks: List[asyncio.Task[CallResult]] = []
        for model, payload in batches.items():
            for idx0, msgs0 in payload:
                tasks.append(asyncio.create_task(_call_one(idx0, model, msgs0, {})))
        for idx, model, messages, extra in individuals:
            tasks.append(asyncio.create_task(_call_one(idx, model, messages, extra)))

        if not tasks:
            return []

        effective_show = SHOW_PROGRESS if show_progress is None else show_progress
        disable_bar = (not effective_show) or (not stream and len(tasks) == 1)
        results: List[CallResult] = []
        for _ in tqdm(
            asyncio.as_completed(tasks),
            total=len(tasks),
            desc=desc or f"Processing {len(tasks)}",
            disable=disable_bar,
        ):
            results.append(await _)
        results.sort(key=lambda r: r.index)
        if export == "results":
            return results
        return [r.content or "" for r in results]

    finally:
        # Ensure Router is shut down. Do NOT shutdown the default executor here;
        # this function may run inside a long-lived loop (e.g., FastAPI) and shutting
        # it down causes subsequent run_in_executor calls to fail with "Executor shutdown".
        await _shutdown_router(router)
        # Persist warm-start metrics (latest only)
        if ENABLE_WARM_START_METRICS and _warm_latencies:
            try:
                from statistics import median
                from pathlib import Path as _P
                _P(WARM_METRICS_PATH).parent.mkdir(parents=True, exist_ok=True)
                out = {"timestamp_started": __import__("datetime").datetime.utcnow().isoformat(), "models": {}}
                for m, arr in _warm_latencies.items():
                    arr2 = arr[:WARM_FIRST_N]
                    arr2s = sorted(arr2)
                    p50 = median(arr2s) if arr2s else 0
                    p95 = arr2s[min(len(arr2s) - 1, int(len(arr2s) * 0.95))] if arr2s else 0
                    out["models"][m] = {"first_10_latencies": arr2s, "p50_ms": p50, "p95_ms": p95}
                _P(WARM_METRICS_PATH).write_text(json.dumps(out, indent=2))
            except Exception:
                pass

# -----------------------------------------------------------------------------
# Demo / CLI
# -----------------------------------------------------------------------------
async def demo() -> List[CallResult]:
    """Demo keeps only network-accessible images to avoid local file deps."""
    prompts = [
        "What is the capital of France?",
        "Calculate 15+27+38",
        "What is 3 + 5? Return JSON: {question:string,answer:number}",
        "What is this animal eating? https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/Grosser_Panda.JPG/960px-Grosser_Panda.JPG",
        "Describe https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Labrador_Retriever_portrait.jpg/960px-Labrador_Retriever_portrait.jpg and https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/Cat_November_2010-1a.jpg/960px-Cat_November_2010-1a.jpg",
        "Describe this image: tests/stage07_manual/images/smoke/panda.png"
    ]
    return await litellm_call(
        prompts,
        default_model=DEFAULT_MODEL,
        wrap_json=False,
        request_timeout=20,
        num_retries=0,
        show_progress=False,
        concurrency=4,
        image_cache_dir=IMAGE_CACHE_DIR,
        sanitize_data_urls="redact",
    )


def demo_sync() -> List[CallResult]:
    return asyncio.run(demo())


def build_cli():
    import typer

    app = typer.Typer(
        name="litellm_call",
        help=(
            f"Thin async batch runner with image support via LiteLLM Router.\n"
            f"Default model: {DEFAULT_MODEL}\n\n"
            "Examples:\n"
            '  - Single: python litellm_call.py main "What is 2+2?"\n'
            '  - JSON:   python litellm_call.py main --json "Return only {\\"ok\\":true}"\n'
            '  - Batch:  python litellm_call.py main "What is 2+2?" "Capital of France?"\n'
            '  - Images: python litellm_call.py main "Describe /path/to/image.jpg and https://example.com/cat.jpg"\n'
            "  - Files:  python litellm_call.py main @prompts.txt   | @prompts.jsonl | prompts.json\n"
            '  - Stdin:  echo "What is 2+2?" | python litellm_call.py main --stdin\n\n'
            "Note: stream mode prints plain text only (no JSON augmentation).\n"
        ),
    )

    @app.command()
    def main(
        sources: List[str] = typer.Argument(
            None,
            help="Prompts or files containing prompts. Use @file to read a file, or '-' for stdin.",
        ),
        model: str = typer.Option(DEFAULT_MODEL, "--model", "-m", help="Default LiteLLM model name"),
        models: Optional[str] = typer.Option(
            None, "--models", help="Comma-separated list of models for 'one prompt → many models'"
        ),
        stdin: bool = typer.Option(False, "--stdin", help="Read prompts from stdin"),
        jsonl: bool = typer.Option(False, "--jsonl", help="Input is JSON Lines"),
        wrap_json: bool = typer.Option(False, "--wrap-json", help="Wrap non-JSON and include usage/cost"),
        json_flag: bool = typer.Option(False, "--json", help="Shorthand for json_object + wrap"),
        max_parallel: int = typer.Option(DEFAULT_MAX_PARALLEL or 0, "--max-parallel", help="Router semaphore (0=unset)"),
        num_retries: int = typer.Option(DEFAULT_NUM_RETRIES, "--num-retries", help="Router retries"),
        response_format: Optional[str] = typer.Option(None, "--response-format", help="e.g. 'json_object'"),
        request_timeout: Optional[float] = typer.Option(None, "--timeout", help="seconds"),
        stream: bool = typer.Option(False, "--stream", help="Stream output for a single prompt"),
        image_cache_dir: Optional[str] = typer.Option(None, "--image-cache-dir", help="Persistent image cache dir"),
        session_id: Optional[str] = typer.Option(None, "--session-id", help="Attach a session/user id"),
        no_progress: bool = typer.Option(False, "--no-progress", help="Disable progress bar"),
        quiet: bool = typer.Option(False, "--quiet", help="Suppress stdout results (use with --output)"),
        prefix_model: Optional[bool] = typer.Option(
            None, "--prefix-model/--no-prefix-model", help="Prefix outputs with model when using --models"
        ),
        output: Optional[str] = typer.Option(None, "--output", "-o", help="Append results to file"),
        export: str = typer.Option(
            "content", "--export", help="content (default) or results (JSONL)"
        ),
        # Sanitization flags
        sanitize: str = typer.Option(
            "redact",
            "--sanitize",
            help="Sanitize data: URLs in returned request messages: 'redact'|'hash'|'truncate'|'none'",
        ),
        sanitize_chars: int = typer.Option(
            48,
            "--sanitize-chars",
            help="When --sanitize=truncate, keep this many base64 chars at head & tail",
        ),
    ):
        # Build prompt list from args/stdin/files (explicit; no global mutation)
        prompts: List[_Any] = []
        from pathlib import Path as _Path

        if stdin or (sources == ["-"]):
            data = sys.stdin.read()
            for line in data.splitlines():
                prompts.append(json.loads(line) if jsonl else line)

        for src in sources or []:
            if src == "-":
                continue
            if src.startswith("@"):
                src = src[1:]
            path = _Path(src)
            if not path.exists():
                prompts.append(src)
                continue
            if path.suffix.lower() == ".json":
                prompts.extend(json.loads(path.read_text()))
            elif path.suffix.lower() == ".jsonl" or jsonl:
                prompts.extend(json.loads(line) for line in path.read_text().splitlines() if line.strip())
            else:
                prompts.extend(line for line in path.read_text().splitlines() if line.strip())

        if not prompts:
            import typer as _typer
            _typer.echo("No prompts provided.", err=True)
            raise _typer.Exit(1)

        # `--json` implies JSON mode and wrapping
        rf = response_format or ("json_object" if json_flag else None)
        do_wrap = wrap_json or json_flag

        dmpr = max_parallel if max_parallel and max_parallel > 0 else None
        model_list_opt = [m.strip() for m in models.split(",")] if models else None

        results = asyncio.run(
            litellm_call(
                prompts,
                default_model=model,
                wrap_json=do_wrap,
                default_max_parallel_requests=dmpr,
                num_retries=num_retries,
                response_format=rf,
                request_timeout=request_timeout,
                stream=stream,
                models=model_list_opt,
                image_cache_dir=image_cache_dir if image_cache_dir is not None else IMAGE_CACHE_DIR,
                session_id=session_id,
                show_progress=not no_progress,
                sanitize_data_urls=sanitize,
                sanitize_truncate_chars=sanitize_chars,
                export=export,
            )
        )

        # Output formatting
        import typer as _typer

        if export == "results":
            # Print JSONL records: index, model, sanitized messages, kwargs, content, error
            def _rec(r):
                return {
                    "index": getattr(r, "index", None),
                    "model": getattr(getattr(r, "request", object()), "model", None),
                    "messages": getattr(getattr(r, "request", object()), "messages", None),
                    "kwargs": getattr(getattr(r, "request", object()), "kwargs", None),
                    "content": getattr(r, "content", None),
                    "error": None if getattr(r, "exception", None) is None else str(getattr(r, "exception", None)),
                }

            lines_jsonl = [json.dumps(_rec(r), ensure_ascii=False) for r in results]  # type: ignore[arg-type]
            if output:
                try:
                    with open(output, "a", encoding="utf-8") as f:
                        for line in lines_jsonl:
                            f.write(line + "\n")
                except Exception as e:
                    _typer.echo(f"Failed to write output: {e}", err=True)
            if not quiet:
                for line in lines_jsonl:
                    _typer.echo(line)
            return

        # Default: human-readable content strings
        def _to_line(x):
            return x if isinstance(x, str) else (x.content or "")
        lines = [_to_line(r) for r in results]

        # Optional prefix per model when using --models
        if model_list_opt and (prefix_model if prefix_model is not None else True):
            labels: List[str] = []
            for _ in prompts:
                labels.extend(model_list_opt)
            if len(labels) == len(lines):
                lines = [f"[{lab}] {line}" for lab, line in zip(labels, lines)]

        if output:
            try:
                with open(output, "a", encoding="utf-8") as f:
                    for line in lines:
                        f.write(line + "\n")
            except Exception as e:
                _typer.echo(f"Failed to write output: {e}", err=True)

        if not quiet:
            for line in lines:
                _typer.echo(line)

    @app.command("sanity")
    def sanity(
        model: str = typer.Option(DEFAULT_MODEL, "--model", "-m", help="Model to use for the sanity check"),
        wrap_json: bool = typer.Option(False, "--wrap-json", help="Wrap non-JSON + include metadata"),
        request_timeout: Optional[float] = typer.Option(None, "--timeout", help="seconds"),
    ):
        """Return only {"ok":true} as JSON; exit 0 iff ok=true."""
        prompt = 'Return only {"ok":true} as JSON.'
        results = asyncio.run(
            litellm_call(
                [prompt],
                default_model=model,
                wrap_json=wrap_json,
                response_format="json_object",
                request_timeout=request_timeout,
                num_retries=0,
                show_progress=False,
                concurrency=1,
            )
        )
        out = (results[0] if results and isinstance(results[0], str) else (results[0].content if results else ""))
        import typer as _typer
        _typer.echo(out)

        ok = False
        try:
            data = json.loads((out or "").strip())
            if isinstance(data, dict):
                ok = data.get("ok") is True or (
                    isinstance(data.get("content"), dict) and data["content"].get("ok") is True
                )
        except Exception:
            ok = False

        raise _typer.Exit(code=0 if ok else 2)

    return app


cli_app = build_cli()

if __name__ == "__main__":
    # With no args: run the async demo (debug-friendly). With args: use the CLI.
    if len(sys.argv) == 1:
        os.environ.setdefault("LITELLM_NO_PROGRESS", "1")  # cleaner stepping in debuggers
        results = asyncio.run(demo())
        for r in results:
            print(r.content or "")
        raise SystemExit(0)
    else:
        # Ergonomics: if called without an explicit subcommand, default to `main`
        argv = sys.argv
        args = argv[1:]
        if args and (not args[0].startswith("-")) and args[0] not in {"main", "sanity"}:
            sys.argv = [argv[0], "main", *args]
        cli_app()
        raise SystemExit(0)
# Defensive: sanitize excessive callback accumulation in long-lived runs
def _sanitize_litellm_callbacks(max_allowed: int = 5):
    try:
        for attr in ("callbacks", "success_callback", "failure_callback", "input_callback", "service_callback"):
            seq = getattr(_litellm, attr, None)
            if isinstance(seq, list) and len(seq) > max_allowed:
                del seq[:-max_allowed]
    except Exception:
        pass
