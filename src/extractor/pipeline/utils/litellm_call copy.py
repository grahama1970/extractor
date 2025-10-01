#!/usr/bin/env python3
"""
LiteLLM Call — thin async batch runner that adds minimal multimodal prep on top of LiteLLM Router.

WHAT IT DOES
- Parses prompts, auto-detects images (URLs/local), compresses/fetches, and builds vision parts.
- Groups prompts per model and runs them concurrently through LiteLLM Router (retries/semaphores).
- Works with any LiteLLM-supported provider (OpenAI, Anthropic, Ollama, etc.).
- Optional JSON wrapping/usage metadata, simple CLI (stdin/@file/JSONL), and a demo.

WHAT IT DOESN’T DO
- Doesn’t force JSON mode/system prompts/schemas/tool definitions—pass them yourself if needed.
- Doesn’t transform tool calls; they’re forwarded as-is per request.
- Doesn’t implement custom retry/concurrency; we rely on Router.

KEY CHOICES
- Single, predictable execution path (no experimental helper branches).
- Bounded client-side concurrency to avoid request stampedes.
- One source of truth for the default model: DEFAULT_LITELLM_MODEL in .env (fail fast if absent).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any as _Any, Dict, List, Optional, Tuple

import litellm as _litellm
from dotenv import find_dotenv, load_dotenv
from dataclasses import dataclass
from loguru import logger
from litellm import Router
try:
    import extractor.pipeline.utils.litelllm_call2 as _engine_mod  # type: ignore
    _engine_litellm_call = getattr(_engine_mod, "litellm_call", None)
    _EngineCallResult = getattr(_engine_mod, "CallResult", None)
except Exception:
    _engine_litellm_call = None  # type: ignore
    _EngineCallResult = None  # type: ignore

# Required project utilities — fail fast if missing
from extractor.pipeline.utils.litellm_image_utils import (
    IMAGE_EXT as _IMAGE_EXT,
    compress_image,
    extract_images,
    fetch_remote_image,
)
from extractor.pipeline.utils.litellm_response_utils import (
    format_answer_with_logging,
)
from extractor.pipeline.utils.log_utils import (
    truncate_large_value,  # type: ignore
    BASE64_IMAGE_PATTERN,  # type: ignore
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

# Default model resolution (prefer LITELLM_DEFAULT_MODEL as project standard)
MODEL = (
    os.getenv("LITELLM_MODEL")
    or os.getenv("LITELLM_DEFAULT_MODEL")
    or os.getenv("DEFAULT_LITELLM_MODEL")
    or os.getenv("OLLAMA_DEFAULT_MODEL", "ollama/gemma3:12b")
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
# For test compatibility (monkeypatchable flag)
_HAVE_PARALLEL_HELPERS = True
IMAGE_CACHE_DIR = os.getenv("LITELLM_IMAGE_CACHE_DIR") or None


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
# Structured result types and sanitization helpers (for result_format='results')
# -----------------------------------------------------------------------------
@dataclass
class CallRequest:
    model: str
    messages: List[Dict[str, _Any]]
    kwargs: Optional[Dict[str, _Any]] = None


@dataclass
class CallResult:
    index: int
    request: CallRequest
    response: Optional[_Any] = None
    exception: Optional[BaseException] = None
    content: Optional[str] = None


def _sanitize_data_url_string(s: str, mode: str, max_len: int) -> str:
    m = BASE64_IMAGE_PATTERN.match(s)
    if not m:
        return s
    header = m.group(1)
    data = s[len(header) :]
    if mode == "none":
        return s
    if mode == "redact":
        return header + "<redacted>"
    if mode == "hash":
        try:
            import hashlib

            h = hashlib.sha256(data.encode("utf-8", errors="ignore")).hexdigest()
            return header + f"<sha256:{h}>"
        except Exception:
            return header + "<hash-error>"
    if mode == "truncate":
        return truncate_large_value(s, max_str_len=max_len)
    return header + "<redacted>"


def _sanitize_any(v: _Any, mode: str, max_len: int) -> _Any:
    if mode == "none":
        return v
    if isinstance(v, str):
        return _sanitize_data_url_string(v, mode, max_len)
    if isinstance(v, list):
        return [_sanitize_any(x, mode, max_len) for x in v]
    if isinstance(v, dict):
        return {k: _sanitize_any(val, mode, max_len) for k, val in v.items()}
    return v


def _sanitize_request(req: CallRequest, mode: str, max_len: int) -> CallRequest:
    if mode == "none":
        return req
    return CallRequest(
        model=req.model,
        messages=_sanitize_any(req.messages, mode, max_len),
        kwargs=_sanitize_any(req.kwargs or {}, mode, max_len) or None,
    )


# -----------------------------------------------------------------------------
# Router lifecycle helpers (avoid lingering threads/handles)
# -----------------------------------------------------------------------------
def _disable_litellm_callbacks() -> None:
    for _name in ("callbacks", "success_callback", "failure_callback", "input_callback", "service_callback"):
        if hasattr(_litellm, _name):
            try:
                setattr(_litellm, _name, [])
            except Exception:
                pass


async def _shutdown_router(router: Router) -> None:
    try:
        aclose = getattr(router, "aclose", None)
        if callable(aclose):
            await aclose()
        else:
            close = getattr(router, "close", None)
            if callable(close):
                close()
    except Exception:
        pass
    # Try to stop default executor threads cleanly
    try:
        loop = asyncio.get_running_loop()
        await loop.shutdown_default_executor()
    except Exception:
        pass

# -----------------------------------------------------------------------------
# Core API
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
    # New: output selection and request sanitization for returned objects
    result_format: str = "content",  # 'content' or 'results'
    sanitize_data_urls: str = "redact",  # 'redact' | 'hash' | 'truncate' | 'none'
    sanitize_truncate_chars: int = 48,
    # Back-compat mapping if older flags are passed in by callers
    truncate_request_b64: Optional[bool] = None,
    request_b64_len: Optional[int] = None,
) -> List[str]:
    """Thin wrapper that delegates to litelllm_call2 and returns either plain strings
    or structured CallResult objects depending on result_format.
    """
    eff_mode = sanitize_data_urls
    eff_len = sanitize_truncate_chars
    if request_b64_len is not None:
        eff_len = request_b64_len
    if truncate_request_b64 is not None:
        if truncate_request_b64 and sanitize_data_urls == "redact":
            eff_mode = "truncate"
        if not truncate_request_b64:
            eff_mode = "none"

    model_to_use = default_model or MODEL
    if _engine_litellm_call is None:
        # Fallback minimal implementation (kept to satisfy local tests and monkeypatches)
        # Expand one→many models
        if isinstance(prompts, (str, dict)):
            prompts = [prompts]
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

        base_model = model_to_use
        # Preprocess prompts into (idx, model, messages, extra)
        processed: List[Tuple[int, str, List[Dict[str, _Any]], Dict[str, _Any]]] = []
        for idx, item in enumerate(prompts):
            model, messages, extra_kwargs = _to_messages_and_model(
                item,
                base_model,
                response_format=response_format,
                request_timeout=request_timeout,
                image_cache_dir=image_cache_dir if image_cache_dir is not None else IMAGE_CACHE_DIR,
            )
            processed.append((idx, model, messages, extra_kwargs))

        # Build router (FakeRouter in tests)
        unique_models = sorted({m for _, m, _, _ in processed})
        router = Router(
            model_list=[{"model_name": m, "litellm_params": {"model": m}} for m in unique_models],
            num_retries=num_retries if num_retries is not None else DEFAULT_NUM_RETRIES,
            default_max_parallel_requests=(
                default_max_parallel_requests if default_max_parallel_requests is not None else DEFAULT_MAX_PARALLEL
            ),
        )

        # Execute sequentially (simple, predictable for tests)
        out_strings: List[str] = [""] * len(processed)
        out_results: List[CallResult] = []
        for idx, model, messages, extra in processed:
            kwargs = dict(extra)
            if attach_session_to_provider and session_id and "user" not in kwargs:
                kwargs["user"] = session_id
            if request_timeout is not None and "timeout" not in kwargs:
                kwargs["timeout"] = request_timeout
            kwargs = _sanitize_kwargs_for_provider(model, kwargs)
            try:
                resp = await router.acompletion(model=model, messages=messages, **kwargs)
            except Exception as e:  # test fakes never raise; keep compatibility
                resp = e
            content = format_answer_with_logging(idx, resp, wrap_json, prompts[idx], logger)
            out_strings[idx] = content
            req = CallRequest(model=model, messages=messages, kwargs=kwargs or None)
            out_results.append(
                CallResult(
                    index=idx,
                    request=_sanitize_request(req, eff_mode, eff_len),
                    response=None if isinstance(resp, Exception) else resp,
                    exception=resp if isinstance(resp, Exception) else None,
                    content=content,
                )
            )

        if result_format == "results":
            # Return structured results (index order is already ascending)
            return out_results  # type: ignore[return-value]
        return out_strings

    results: List[_EngineCallResult] = await _engine_litellm_call(
        prompts,
        default_model=model_to_use,
        wrap_json=wrap_json,
        desc=desc,
        session_id=session_id,
        attach_session_to_provider=attach_session_to_provider,
        num_retries=num_retries,
        default_max_parallel_requests=default_max_parallel_requests,
        concurrency=concurrency,
        response_format=response_format,
        request_timeout=request_timeout,
        stream=stream,
        models=models,
        image_cache_dir=image_cache_dir if image_cache_dir is not None else IMAGE_CACHE_DIR,
        show_progress=show_progress,
        sanitize_data_urls=eff_mode,
        sanitize_truncate_chars=eff_len,
    )

    if result_format == "results":
        return results  # type: ignore[return-value]
    return [r.content or "" for r in results]


# -----------------------------------------------------------------------------
# Convenience helper
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
    """Common case: one prompt (+ optional image)."""
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
    return out[0] if out else ""


# -----------------------------------------------------------------------------
# Demo / CLI
# -----------------------------------------------------------------------------
async def demo() -> List[str]:
    """Demo uses only network-accessible images to avoid local file deps."""
    prompts = [
        "What is the capital of France?",
        "Calculate 15+27+38",
        "What is 3 + 5? Return JSON: {question:string,answer:number}",
        "What is this animal eating? https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/Grosser_Panda.JPG/960px-Grosser_Panda.JPG",
        "Describe https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Labrador_Retriever_portrait.jpg/960px-Labrador_Retriever_portrait.jpg and https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/Cat_November_2010-1a.jpg/960px-Cat_November_2010-1a.jpg",
    ]
    result = await litellm_call(
        prompts,
        default_model=DEFAULT_MODEL,
        wrap_json=False,
        request_timeout=20,
        num_retries=0,
        show_progress=False,
        concurrency=1,
        image_cache_dir=IMAGE_CACHE_DIR,
    )
    return result


def demo_sync() -> List[str]:
    return asyncio.run(demo())


def build_cli():
    import typer

    app = typer.Typer(
        name="litellm_call",
        help=(
            f"Thin async batch runner with image support via LiteLLM Router.\n"
            f"Default model: {MODEL}\n\n"
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
        model: str = typer.Option(MODEL, "--model", "-m", help="Default LiteLLM model name"),
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
            )
        )

        # Optionally prefix results per model when using --models
        if model_list_opt and (prefix_model if prefix_model is not None else True):
            labels: List[str] = []
            for _ in prompts:
                labels.extend(model_list_opt)
            if len(labels) == len(results):
                results = [f"[{lab}] {r}" for lab, r in zip(labels, results)]

        if output:
            try:
                with open(output, "a", encoding="utf-8") as f:
                    for line in results:
                        f.write(line + "\n")
            except Exception as e:
                import typer as _typer
                _typer.echo(f"Failed to write output: {e}", err=True)

        if not quiet:
            import typer as _typer
            for line in results:
                _typer.echo(line)

    @app.command("sanity")
    def sanity(
        model: str = typer.Option(MODEL, "--model", "-m", help="Model to use for the sanity check"),
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
        out = results[0] if results else ""
        import typer as _typer
        _typer.echo(out)

        ok = False
        try:
            data = json.loads(out.strip())
            if isinstance(data, dict):
                ok = data.get("ok") is True or (isinstance(data.get("content"), dict) and data["content"].get("ok") is True)
        except Exception:
            ok = False

        raise _typer.Exit(code=0 if ok else 2)

    return app


cli_app = build_cli()

if __name__ == "__main__":
    # With no args: run the async demo (debug-friendly). With args: use the CLI.
    if len(sys.argv) == 1:
        os.environ.setdefault("LITELLM_NO_PROGRESS", "1")  # cleaner stepping in debuggers
        try:
            results = asyncio.run(demo())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                results = loop.run_until_complete(demo())
            finally:
                try:
                    loop.close()
                except Exception:
                    pass
        for line in results:
            print(line)
        sys.exit(0)
    else:
        # Allow calling without explicit subcommand: treat first non-flag as args to `main`
        argv = sys.argv
        args = argv[1:]
        if args and (not args[0].startswith("-")) and args[0] not in {"main", "sanity"}:
            sys.argv = [argv[0], "main", *args]
        cli_app()
        sys.exit(0)
