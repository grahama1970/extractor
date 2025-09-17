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
from dataclasses import dataclass
from typing import Any as _Any, Dict, List, Optional, Tuple

import litellm as _litellm
from dotenv import find_dotenv, load_dotenv
from loguru import logger
from tqdm.asyncio import tqdm
from litellm import Router

# Required project utilities — fail fast if missing
from extractor.pipeline.utils.litellm_image_utils import (
    IMAGE_EXT as _IMAGE_EXT,
    compress_image,
    extract_images,
    fetch_remote_image,
)
from extractor.pipeline.utils.litellm_response_utils import (
    assemble_stream_text,
    format_answer_with_logging,
)

# Optional cache initializer — no-op if unavailable
try:
    from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache  # type: ignore
except ImportError:  # pragma: no cover
    initialize_litellm_cache = lambda: None  # noqa: E731


# -----------------------------------------------------------------------------
# Logging & environment
# -----------------------------------------------------------------------------
logger.remove()
logger.add(sys.stderr, level="WARNING")

# Best-effort .env loading; no exceptions
_ = load_dotenv(find_dotenv(usecwd=True) or None)

# Single source of truth for the default model — fail fast if missing
DEFAULT_MODEL = os.getenv("LITELLM_DEFAULT_MODEL")
if not DEFAULT_MODEL:
    raise RuntimeError(
        "LITELLM_DEFAULT_MODEL must be set in your .env "
        "(e.g., LITELLM_DEFAULT_MODEL=gemini/gemini-2.5-flash)."
    )

# Drop unsupported provider params unless explicitly disabled
_litellm.drop_params = os.getenv("LITELLM_DROP_PARAMS", "true").lower() in {"1", "true", "yes", "y"}
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
def _is_gemini_model(model_name: Optional[str]) -> bool:
    m = (model_name or "").lower()
    return m.startswith("gemini/") or "/gemini" in m or m == "gemini"


def _sanitize_kwargs_for_provider(model: str, kwargs: Dict[str, _Any]) -> Dict[str, _Any]:
    """
    Normalize/strip provider-specific params that can cause errors.

    - Gemini: remove token-limit keys (max_tokens, max_output_tokens).
    """
    if _is_gemini_model(model):
        kwargs.pop("max_tokens", None)
        kwargs.pop("max_output_tokens", None)
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
    """
    Returns:
      - model: provider/model string
      - messages: OpenAI-style message list
      - extra_kwargs: any per-request params beyond (model, messages)

    Branching:
      - If `item` is a dict with `messages`: treat it as a fully-controlled request; everything
        except {model,messages} becomes per-request kwargs.
      - If `item` is a dict without `messages`: treat it as a *shorthand* record with optional
        {text, image, model}. We build a single user message from text plus any detected images.
      - Otherwise (str/other): parse images from the text, assume `default_model`, and build one user message.
    """
    extra_kwargs: Dict[str, _Any] = {}

    # Full control: prebuilt messages (+ per-request params)
    if isinstance(item, dict) and "messages" in item:
        model = item.get("model", default_model)
        messages = item["messages"]
        for k, v in item.items():
            if k not in {"model", "messages"}:
                extra_kwargs[k] = v
        if response_format:
            extra_kwargs.setdefault("response_format", {"type": response_format})
        if request_timeout is not None:
            extra_kwargs.setdefault("timeout", request_timeout)
        return model, messages, extra_kwargs

    # Shorthand structure: {text?, image?, model?}
    if isinstance(item, dict):
        text = str(item.get("text", ""))
        images = [str(item["image"])] if "image" in item else []
        model = item.get("model", default_model)
    else:
        images, text = extract_images(str(item))
        model = default_model

    # Build multimodal content for a single user message
    content_parts: List[Dict[str, _Any]] = []
    if text:
        content_parts.append({"type": "text", "text": text})
    for img in images:
        url = (
            fetch_remote_image(img, cache_dir=image_cache_dir)
            if img.startswith("http")
            else compress_image(img, cache_dir=image_cache_dir)
        )
        if url:
            content_parts.append({"type": "image_url", "image_url": {"url": url}})

    messages = [{"role": "user", "content": content_parts or [{"type": "text", "text": ""}]}]
    if response_format:
        extra_kwargs.setdefault("response_format", {"type": response_format})
    if request_timeout is not None:
        extra_kwargs.setdefault("timeout", request_timeout)
    return model, messages, extra_kwargs


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
) -> List[CallResult]:
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
        """Return a sanitized shallow copy of messages for inclusion in CallResult."""
        mode = (sanitize_data_urls or "redact").lower()
        if mode == "none":
            return messages  # return as-is
        sanitized: List[Dict[str, _Any]] = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            if isinstance(content, list):
                new_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "image_url":
                        img = dict(part.get("image_url") or {})
                        url = img.get("url")
                        if isinstance(url, str):
                            img["url"] = _sanitize_data_url(url)
                        new_parts.append({"type": "image_url", "image_url": img})
                    else:
                        new_parts.append(part if isinstance(part, dict) else part)
                sanitized.append({"role": role, "content": new_parts})
            else:
                sanitized.append({"role": role, "content": content})
        return sanitized

    # -------------------------------------------------------------------------
    if isinstance(prompts, (str, dict)):
        prompts = [prompts]

    base_model = default_model or DEFAULT_MODEL
    if not base_model:
        raise RuntimeError("No default model configured. Set LITELLM_DEFAULT_MODEL or pass default_model.")

    if attach_session_to_provider is None:
        attach_session_to_provider = DEFAULT_ATTACH_SESSION

    num_retries = DEFAULT_NUM_RETRIES if num_retries is None else num_retries
    if concurrency is not None and default_max_parallel_requests is None:
        default_max_parallel_requests = concurrency
    default_max_parallel_requests = (
        DEFAULT_MAX_PARALLEL if default_max_parallel_requests is None else default_max_parallel_requests
    )
    image_cache_dir = image_cache_dir if image_cache_dir is not None else IMAGE_CACHE_DIR

    # One prompt → many models fan-out
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

    # Group batchables vs. individuals
    batches: Dict[str, List[Tuple[int, List[Dict[str, _Any]]]]] = {}
    individuals: List[Tuple[int, str, List[Dict[str, _Any]], Dict[str, _Any]]] = []

    for idx, model, messages, extra_kwargs in processed:
        if extra_kwargs:
            individuals.append((idx, model, messages, extra_kwargs))
        else:
            batches.setdefault(model, []).append((idx, messages))

    # Router (create once; ensure we always shut it down)
    unique_models = sorted({m for _, m, _, _ in processed})

    # Ensure LiteLLM background callbacks can't keep the process alive
    for _name in ("callbacks", "success_callback", "failure_callback", "input_callback", "service_callback"):
        if hasattr(_litellm, _name):
            setattr(_litellm, _name, [])

    router = Router(
        model_list=[{"model_name": m, "litellm_params": {"model": m}} for m in unique_models],
        num_retries=num_retries,
        default_max_parallel_requests=default_max_parallel_requests,
    )

    try:
        # Compute effective client concurrency aligned with Router cap
        limit_client = concurrency or (DEFAULT_MAX_PARALLEL or 8)
        limit_router = default_max_parallel_requests or (DEFAULT_MAX_PARALLEL or 8)
        limit = min(limit_client, limit_router)

        logger.info(
            "litellm_call: models=[%s], concurrency=%s, tasks=%d",
            ",".join(unique_models) or "(none)",
            limit,
            len(processed),
        )

        # Streaming fast-path: assemble text only (no JSON augmentation), but still return a CallResult
        if stream and len(processed) == 1 and not individuals and len(batches) == 1:
            model = unique_models[0]
            idx0, msgs0 = next(iter(batches[model]))
            kwargs: Dict[str, _Any] = {}
            if attach_session_to_provider and session_id:
                kwargs["user"] = session_id
            if request_timeout is not None:
                kwargs["timeout"] = request_timeout

            try:
                resp_stream = await router.acompletion(model=model, messages=msgs0, stream=True, **kwargs)
                content = await assemble_stream_text(resp_stream)
                req_msgs = _sanitize_messages_for_return(msgs0)
                return [
                    CallResult(
                        index=idx0,
                        request=CallRequest(model=model, messages=req_msgs, kwargs=kwargs or None),
                        response=None,
                        exception=None,
                        content=content,
                    )
                ]
            except TypeError:
                # router.acompletion doesn't accept stream in this version; fall back to non-stream
                resp = await router.acompletion(model=model, messages=msgs0, **kwargs)
                content = format_answer_with_logging(idx0, resp, wrap_json, prompts[idx0], logger)
                req_msgs = _sanitize_messages_for_return(msgs0)
                return [
                    CallResult(
                        index=idx0,
                        request=CallRequest(model=model, messages=req_msgs, kwargs=kwargs or None),
                        response=resp,
                        exception=None,
                        content=content,
                    )
                ]

        # Single path: bounded concurrency over acompletion
        sem = asyncio.Semaphore(limit)

        async def _call_one(
            idx: int, model: str, messages: List[Dict[str, _Any]], extra: Dict[str, _Any]
        ) -> CallResult:
            kwargs = dict(extra)
            if attach_session_to_provider and session_id and "user" not in kwargs:
                kwargs["user"] = session_id
            if request_timeout is not None and "timeout" not in kwargs:
                kwargs["timeout"] = request_timeout
            kwargs = _sanitize_kwargs_for_provider(model, kwargs)
            # Sanitize request for return (do NOT mutate original messages)
            req_msgs = _sanitize_messages_for_return(messages)
            req = CallRequest(model=model, messages=req_msgs, kwargs=(kwargs or None) if kwargs else None)
            async with sem:
                try:
                    resp = await router.acompletion(model=model, messages=messages, **kwargs)
                    content = format_answer_with_logging(idx, resp, wrap_json, prompts[idx], logger)
                    return CallResult(index=idx, request=req, response=resp, exception=None, content=content)
                except BaseException as e:
                    logger.exception("litellm_call task failed (idx=%s, model=%s)", idx, model)
                    content = format_answer_with_logging(idx, e, wrap_json, prompts[idx], logger)
                    return CallResult(index=idx, request=req, response=None, exception=e, content=content)

        tasks: List[asyncio.Task[CallResult]] = []
        for model, payload in batches.items():
            for idx0, msgs0 in payload:
                tasks.append(asyncio.create_task(_call_one(idx0, model, msgs0, {})))
        for idx, model, messages, extra in individuals:
            tasks.append(asyncio.create_task(_call_one(idx, model, messages, extra)))

        if not tasks:
            return []

        # Progress bar on completion order; then collect results (returned ordered by original index)
        effective_show = SHOW_PROGRESS if show_progress is None else show_progress
        disable_bar = (not effective_show) or (not stream and len(tasks) == 1)
        for _ in tqdm(
            asyncio.as_completed(tasks),
            total=len(tasks),
            desc=desc or f"Processing {len(tasks)}",
            disable=disable_bar,
        ):
            await _

        results = [t.result() for t in tasks]
        results.sort(key=lambda r: r.index)
        return results

    finally:
        # Ensure Router is shut down so the event loop can exit cleanly (prevents "hang after printing")
        await _shutdown_router(router)
        # Deterministic cleanup for debugger environments: stop idle ThreadPoolExecutor workers
        try:
            loop = asyncio.get_running_loop()
            await loop.shutdown_default_executor()
        except Exception:
            pass


# -----------------------------------------------------------------------------
# Convenience helper (returns a string for easy drop-in use)
# -----------------------------------------------------------------------------
async def llm(
    prompt: str,
    *,
    model: Optional[str] = None,
    image: Optional[str] = None,
    json: bool = False,
    timeout: Optional[float] = None,
    session_id: Optional[str] = None,
) -> str:
    """Common case: one prompt (+ optional image). Returns human-ready text."""
    item: Dict[str, _Any] = {"text": prompt}
    if image:
        item["image"] = image
    if model:
        item["model"] = model

    response_format = "json_object" if json else None
    out = await litellm_call(
        [item],
        default_model=DEFAULT_MODEL,
        wrap_json=json,
        response_format=response_format,
        request_timeout=timeout,
        session_id=session_id,
        show_progress=False,
    )
    if not out:
        return ""
    return out[0].content or ""


# -----------------------------------------------------------------------------
# Demo / CLI
# -----------------------------------------------------------------------------
async def demo() -> List[CallResult]:
    """Demo uses only network-accessible images to avoid local file deps."""
    prompts = [
        "What is the capital of France?",
        "Calculate 15+27+38",
        "What is 3 + 5? Return JSON: {question:string,answer:number}",
        "What is this animal eating? https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/Grosser_Panda.JPG/960px-Grosser_Panda.JPG",
        "Describe https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Labrador_Retriever_portrait.jpg/960px-Labrador_Retriever_portrait.jpg and https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/Cat_November_2010-1a.jpg/960px-Cat_November_2010-1a.jpg",
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
    )


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
            )
        )

        # Human output: print CallResult.content
        lines = [r.content or "" for r in results]

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
                import typer as _typer
                _typer.echo(f"Failed to write output: {e}", err=True)

        if not quiet:
            import typer as _typer
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
        out = results[0].content if results else ""
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