#!/usr/bin/env python3

"""
LiteLLM Call - Thin async batch runner that adds multimodal prep on top of LiteLLM Router

WHAT IT DOES:
- Parse prompts, auto-detect images (URLs/local), compress/fetch, and build proper vision message parts
- Batch multiple prompts per model using LiteLLM Router async APIs
- Leverage LiteLLM’s built-in retries and per-deployment concurrency/semaphores
- Works with any LiteLLM-supported model (OpenAI, Anthropic, Ollama, etc.)
- Optionally wraps non-JSON outputs into JSON and augments JSON with usage/cost metadata
- Mixed models in one run: supported (items can specify different models)

WHAT THIS SCRIPT DOES NOT DO:
- It does NOT inject JSON mode, system prompts, schemas, or tool-call definitions.
  If you need strict JSON, include `"response_format": {"type": "json_object"}` (or a system prompt).
- It does NOT transform tool calls. If you pass tools, they will be sent as-is on individual calls (not batched).
- It does NOT implement custom retry/tenacity or custom concurrency. Those are delegated to LiteLLM Router.

WHAT’S DIFFERENT VS ORIGINAL VERSION:
- Uses LiteLLM Router for:
  - Retries (num_retries) via Router instead of a custom tenacity decorator
  - Concurrency/rate-limiting via per-deployment semaphores (max_parallel_requests/rpm/tpm)
  - Per-model batch calls: Router.abatch_completion_one_model_multiple_requests
- Still supports different models per item:
  - Requests are grouped by model and sent as separate batches per model
  - Items with extra per-request params (e.g., temperature/tools) are sent in parallel individually
- Removed hand-rolled “concurrency” control; rely on Router’s concurrency
- Keeps the image auto-detect/compress logic and CLI UX

INPUT FORMS SUPPORTED:
1) Simple string:
   "What's in this image? /path/to/image.jpg"

2) Shorthand dict:
   {"text": "Explain this", "image": "path/to/image.jpg", "model": "gpt-4o-mini"}

3) Full control (sent individually if you include per-request params):
   {
     "model": "gpt-4o-mini",
     "messages": [...],
     "temperature": 0.7,
     "tools": [...]
   }

BATCHING RULES:
- Requests with only model + messages (no extra per-request params) are grouped by model and sent via Router.abatch_completion_one_model_multiple_requests.
- Requests that include extra per-request params (e.g., temperature/tools/response_format/etc.) are sent as individual Router.acompletion calls to preserve request-specific behavior.
- Mixed models in one run are supported; each model gets its own batch.

ENVIRONMENT / DEFAULTS:
- LITELLM_MODEL: Fallback model (default: "ollama/gemma3:12b")
- LITELLM_NUM_RETRIES: Default num_retries for Router calls (default: 3)
- LITELLM_MAX_PARALLEL: Router default_max_parallel_requests (per-deployment semaphore default). Optional.
- LITELLM_ATTACH_SESSION: If "true", pass session_id as `user` to providers (default: true)

Provider-specific envs are still honored by LiteLLM (e.g., OPENAI_API_KEY, OLLAMA_BASE_URL, etc.).

CLI EXAMPLES:
- Single:
  $ python litellm_call.py "What is 2+2?"

- Batch (multiple prompts):
  $ python litellm_call.py "What is 2+2?" "What is the capital of France?"

- Multimodal (auto image detection from local path and URL):
  $ python litellm_call.py "What's in this image? /path/to/image.jpg"
  $ python litellm_call.py "Describe https://example.com/cat.jpg and dog.png"

- From files / stdin:
  $ python litellm_call.py @prompts.txt
  $ python litellm_call.py prompts.json
  $ python litellm_call.py @prompts.jsonl
  $ echo "What is 2+2?" | python litellm_call.py --stdin
"""

import asyncio
import sys
import json
import base64
import io
import os
import re
from pathlib import Path
from typing import List, Tuple, Any, Dict, Optional
from copy import deepcopy

import httpx
from PIL import Image
import litellm as _litellm
from tqdm.asyncio import tqdm
from loguru import logger
from dotenv import load_dotenv, find_dotenv
from urlextract import URLExtract

from strip_tags import strip_tags
from litellm import Router
from extractor.pipeline.utils.image_helpers import (
    IMAGE_EXT as _IMAGE_EXT,
    extract_images as _shared_extract_images,
    safe_image as _shared_safe_image,
    compress_image_cached,
    fetch_remote_image_cached,
)

logger.remove()
logger.add(sys.stderr, level="WARNING")

# Optional: your project’s litellm cache initializer
try:
    from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache
except Exception:
    def initialize_litellm_cache():
        pass

load_dotenv(find_dotenv())
# Do not drop provider-specific params; we pass image_url parts intentionally
_litellm.drop_params = False
initialize_litellm_cache()

# -----------------------------------------------------------------------------
# Defaults / env
# -----------------------------------------------------------------------------
MODEL = os.getenv("LITELLM_MODEL", os.getenv("OLLAMA_DEFAULT_MODEL", "ollama/gemma3:12b"))
IMAGE_EXT = _IMAGE_EXT
extractor = URLExtract()
SHOW_PROGRESS = os.getenv("LITELLM_NO_PROGRESS", "").lower() not in {"1", "true", "yes"}

DEFAULT_NUM_RETRIES = int(os.getenv("LITELLM_NUM_RETRIES", "3"))
DEFAULT_MAX_PARALLEL = os.getenv("LITELLM_MAX_PARALLEL")
DEFAULT_MAX_PARALLEL = int(DEFAULT_MAX_PARALLEL) if DEFAULT_MAX_PARALLEL and DEFAULT_MAX_PARALLEL.isdigit() else None
DEFAULT_ATTACH_SESSION = os.getenv("LITELLM_ATTACH_SESSION", "true").lower() in {"1", "true", "yes", "y"}

# Optional image cache directory (persistent across runs)
_IMAGE_CACHE_DIR = os.getenv("LITELLM_IMAGE_CACHE_DIR") or None

# -----------------------------------------------------------------------------
# Helpers - Images
# -----------------------------------------------------------------------------

def safe_image(path: Path) -> bool:
    return _shared_safe_image(path)


def extract_images(text: str) -> tuple[List[str], str]:
    return _shared_extract_images(text)


def compress_image(path_str: str, max_kb: int = 1000) -> str:
    return compress_image_cached(path_str, max_kb=max_kb, cache_dir=_IMAGE_CACHE_DIR)


def fetch_remote_image(url: str) -> Optional[str]:
    return fetch_remote_image_cached(url, timeout=10, cache_dir=_IMAGE_CACHE_DIR)


## No MIME coercion: pass image data URLs through unchanged


# -----------------------------------------------------------------------------
# Cost / usage helpers
# -----------------------------------------------------------------------------

def _clean_json_code_fences(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _extract_usage_and_cost(resp: Any) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    usage = getattr(resp, "usage", None)

    token_usage = None
    if usage is not None:
        if isinstance(usage, dict):
            token_usage = {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            }
        else:
            token_usage = {
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            }
    if token_usage is not None:
        metadata["token_usage"] = token_usage

    hidden = getattr(resp, "_hidden_params", {}) or {}
    if isinstance(hidden, dict) and "response_cost" in hidden:
        metadata["response_cost"] = hidden.get("response_cost")
    if isinstance(hidden, dict) and "cache_hit" in hidden:
        metadata["cache_hit"] = hidden.get("cache_hit")
    return metadata


def _maybe_augment_json_with_cost(text: str, resp: Any, wrap_non_json: bool = False) -> str:
    cleaned = _clean_json_code_fences(text)
    try:
        parsed = json.loads(cleaned)
    except Exception:
        if wrap_non_json:
            return json.dumps({"content": text, "metadata": _extract_usage_and_cost(resp)}, ensure_ascii=False)
        return text

    metadata = _extract_usage_and_cost(resp)
    if isinstance(parsed, dict):
        if "metadata" in parsed and isinstance(parsed["metadata"], dict):
            parsed["metadata"].update(metadata)
        elif "_metadata" in parsed and isinstance(parsed["_metadata"], dict):
            parsed["_metadata"].update(metadata)
        else:
            parsed["metadata"] = metadata
        return json.dumps(parsed, ensure_ascii=False)

    if wrap_non_json:
        return json.dumps({"content": parsed, "metadata": metadata}, ensure_ascii=False)

    return json.dumps(parsed, ensure_ascii=False)


def _extract_text(resp: Any) -> str:
    # OpenAI-style dict
    if isinstance(resp, dict) and "choices" in resp:
        try:
            ch = resp.get("choices") or []
            if ch:
                msg = ch[0].get("message") or {}
                return str(msg.get("content") or "")
        except Exception:
            pass
    # ModelResponse-like object
    ch_obj = getattr(resp, "choices", None)
    if ch_obj:
        try:
            ch0 = ch_obj[0]
            msg = getattr(ch0, "message", None)
            if msg is not None and getattr(msg, "content", None) is not None:
                content = getattr(msg, "content")
                if isinstance(content, list):
                    parts = []
                    for p in content:
                        if isinstance(p, dict):
                            t = p.get("text") or p.get("content")
                            if isinstance(t, str) and t.strip():
                                parts.append(t.strip())
                    if parts:
                        return "\n".join(parts)
                return str(content)
            txt = getattr(ch0, "text", None)
            if isinstance(txt, str):
                return txt
            # Fallback: some adapters expose text on response.output_text
            ot = getattr(resp, "output_text", None)
            if isinstance(ot, str) and ot.strip():
                return ot
        except Exception:
            pass
    if isinstance(resp, str):
        return resp
    return ""


# -----------------------------------------------------------------------------
# Prompt preprocessing => messages
# -----------------------------------------------------------------------------

def _to_messages_and_model(
    item: Any,
    default_model: str,
    *,
    response_format: Optional[str] = None,
    request_timeout: Optional[float] = None,
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Returns:
      model: str
      messages: List[message]
      extra_kwargs: Dict[str,Any]  # any per-request params beyond (model, messages)
    Behavior:
      - str -> parse for images, build a single user message with text + image parts
      - shorthand dict -> same as str + optional 'image' + model override
      - full dict with 'messages' -> preserve messages; anything else goes into extra_kwargs
    """
    extra_kwargs: Dict[str, Any] = {}

    # Full dict with manual messages
    if isinstance(item, dict) and "messages" in item:
        model = item.get("model", default_model)
        messages = item["messages"]
        # Everything else is per-request params (temperature, tools, etc.)
        for k, v in item.items():
            if k not in {"model", "messages"}:
                extra_kwargs[k] = v
        if response_format:
            extra_kwargs.setdefault("response_format", {"type": response_format})
        if request_timeout is not None:
            extra_kwargs.setdefault("timeout", request_timeout)
        return model, messages, extra_kwargs

    # Shorthand dict
    if isinstance(item, dict):
        text = str(item.get("text", ""))
        images = [str(item["image"])] if "image" in item else []
        model = item.get("model", default_model)
    else:
        images, text = extract_images(str(item))
        model = default_model

    content_parts: List[Dict[str, Any]] = []
    if text:
        content_parts.append({"type": "text", "text": text})
    for img in images:
        url = fetch_remote_image(img) if img.startswith("http") else compress_image(img)
        if url:
            content_parts.append({"type": "image_url", "image_url": {"url": url}})

    messages = [{"role": "user", "content": content_parts or [{"type": "text", "text": ""}]}]
    if response_format:
        extra_kwargs.setdefault("response_format", {"type": response_format})
    if request_timeout is not None:
        extra_kwargs.setdefault("timeout", request_timeout)
    return model, messages, extra_kwargs


# -----------------------------------------------------------------------------
# Core API - uses LiteLLM Router for batching/retries/semaphores
# -----------------------------------------------------------------------------

async def litellm_call(
    prompts: List[Any],
    *,
    wrap_json: bool = False,
    desc: str | None = None,
    session_id: str | None = None,
    attach_session_to_provider: bool | None = None,
    num_retries: Optional[int] = None,
    default_max_parallel_requests: Optional[int] = None,
    concurrency: Optional[int] = None,
    response_format: Optional[str] = None,
    request_timeout: Optional[float] = None,
    stream: bool = False,
    models: Optional[List[str]] = None,
) -> List[str]:
    """
    Run prompts in parallel with automatic image support.
    - Batch per-model requests via Router.abatch_completion_one_model_multiple_requests
    - Send per-request customized calls individually via Router.acompletion
    - Mixed models per run supported (each model gets its own batch)

    Returns list[str] answers, aligned with input order. Errors become "" unless wrap_json=True,
    in which case a structured {"error":{...}} JSON is returned.
    """
    if isinstance(prompts, (str, dict)):
        prompts = [prompts]

    if attach_session_to_provider is None:
        attach_session_to_provider = DEFAULT_ATTACH_SESSION

    num_retries = DEFAULT_NUM_RETRIES if num_retries is None else num_retries
    if concurrency is not None and default_max_parallel_requests is None:
        default_max_parallel_requests = concurrency
    default_max_parallel_requests = (
        DEFAULT_MAX_PARALLEL if default_max_parallel_requests is None else default_max_parallel_requests
    )

    # One prompt → many models (simple, low-brittleness approach):
    if models:
        expanded: List[Any] = []
        for item in prompts:
            for m in models:
                if isinstance(item, dict):
                    it = dict(item)
                    it["model"] = m
                else:
                    it = item
                expanded.append(it)
        prompts = expanded

    # Preprocess all prompts
    processed: List[Tuple[int, str, List[Dict[str, Any]], Dict[str, Any]]] = []
    for idx, item in enumerate(prompts):
        model, messages, extra_kwargs = _to_messages_and_model(
            item, MODEL, response_format=response_format, request_timeout=request_timeout
        )
        processed.append((idx, model, messages, extra_kwargs))

    # Group by model for batchable items (no per-request extra kwargs)
    batches: Dict[str, List[Tuple[int, List[Dict[str, Any]]]]] = {}
    individuals: List[Tuple[int, str, List[Dict[str, Any]], Dict[str, Any]]] = []

    for idx, model, messages, extra_kwargs in processed:
        if extra_kwargs:
            individuals.append((idx, model, messages, extra_kwargs))
        else:
            batches.setdefault(model, []).append((idx, messages))

    # Initialize Router with all required model entries
    unique_models = sorted({m for _, m, _, _ in processed})
    model_list: List[Dict[str, Any]] = [
        {"model_name": m, "litellm_params": {"model": m}} for m in unique_models
    ]

    router = Router(
        model_list=model_list,
        num_retries=num_retries,
        default_max_parallel_requests=default_max_parallel_requests,
    )

    results: List[str] = [""] * len(processed)

    # Optional streaming fast-path: only for a single item without extra kwargs
    if stream and len(processed) == 1 and not individuals and len(batches) == 1:
        model = unique_models[0]
        idx0, msgs0 = next(iter(batches[model]))
        kwargs: Dict[str, Any] = {}
        if attach_session_to_provider and session_id:
            kwargs["user"] = session_id
        if request_timeout is not None:
            kwargs.setdefault("timeout", request_timeout)
        try:
            resp_stream = await router.acompletion(model=model, messages=msgs0, stream=True, **kwargs)
        except TypeError:
            resp = await router.acompletion(model=model, messages=msgs0, **kwargs)
            results[idx0] = _format_answer(idx0, resp, wrap_json, prompts)
            return results

        assembled = []
        try:
            async for chunk in resp_stream:  # type: ignore
                try:
                    delta = chunk["choices"][0]["delta"].get("content")
                    if delta:
                        print(delta, end="", flush=True)
                        assembled.append(delta)
                        continue
                except Exception:
                    pass
                text = (
                    getattr(getattr(chunk, "choices", [None])[0], "text", None)
                    if hasattr(chunk, "choices") else None
                )
                if isinstance(text, str):
                    print(text, end="", flush=True)
                    assembled.append(text)
        except Exception:
            pass
        print()
        results[idx0] = "".join(assembled)
        return results

    # Submit all calls via Router.acompletion (unified path)
    async def _call_one(idx: int, model: str, messages: List[Dict[str, Any]], extra: Dict[str, Any]) -> Tuple[int, Any]:
        kwargs = dict(extra)
        if attach_session_to_provider and session_id and "user" not in kwargs:
            kwargs["user"] = session_id
        if request_timeout is not None and "timeout" not in kwargs:
            kwargs["timeout"] = request_timeout
        try:
            resp = await router.acompletion(model=model, messages=messages, **kwargs)
            return idx, resp
        except Exception as e:
            return idx, e

    tasks: List[asyncio.Task[Tuple[int, Any]]] = []
    # From batchable items
    for model, payload in batches.items():
        for idx0, msgs0 in payload:
            tasks.append(asyncio.create_task(_call_one(idx0, model, msgs0, {})))
    # From individual items
    for idx, model, messages, extra in individuals:
        tasks.append(asyncio.create_task(_call_one(idx, model, messages, extra)))

    if not tasks:
        return results

    for _ in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc=desc or "Processing", disable=not SHOW_PROGRESS):
        await _

    for t in tasks:
        idx, resp = t.result()
        results[idx] = _format_answer(idx, resp, wrap_json, prompts)

    return results


async def _progress_wait(
    batch_tasks: List[asyncio.Task],
    indiv_tasks: List[asyncio.Task],
):
    # Iterate as tasks complete for tqdm
    pending = set(batch_tasks + indiv_tasks)
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for _ in done:
            yield True


def _format_answer(idx: int, resp: Any, wrap_json: bool, prompts: List[Any]) -> str:
    if isinstance(resp, Exception):
        # If model lacks vision, surface a clearer message if possible
        m = str(resp).lower()
        if any(kw in m for kw in ["does not support", "unsupported", "image input", "image_url", "no vision", "vision not", "invalid type for", "doesn't support"]):
            logger.warning(f"LiteLLM call failed for Q{idx}: {type(resp).__name__}: {resp}")
        if wrap_json:
            return json.dumps({
                "error": {
                    "type": type(resp).__name__,
                    "message": str(resp)[:400]
                }
            }, ensure_ascii=False)
        return ""
    try:
        answer = _extract_text(resp)
        final_answer = _maybe_augment_json_with_cost(answer, resp, wrap_non_json=wrap_json)
    except Exception as e:
        logger.warning(f"Failed to parse response for Q{idx}: {e}")
        final_answer = "" if not wrap_json else json.dumps({"error": {"type": type(e).__name__, "message": str(e)[:400]}}, ensure_ascii=False)

    safe_prompt = deepcopy(prompts[idx])
    if isinstance(safe_prompt, dict) and "api_key" in safe_prompt:
        safe_prompt["api_key"] = "***"
    logger.info(f"Q{idx}: {str(safe_prompt)[:50]}... -> {final_answer[:100]}...")
    return final_answer


# -----------------------------------------------------------------------------
# Demo / CLI
# -----------------------------------------------------------------------------

async def demo() -> List[str]:
    prompts = [
        "What is the capital of France?",
        "Calculate 15+27+38",
        "What is 3 + 5? Return JSON: {question:string,answer:number}",
        "What is this animal eating? proof_of_concept/ollama_turbo/images/image2.png",
        "Describe https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Labrador_Retriever_portrait.jpg/960px-Labrador_Retriever_portrait.jpg and https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/Cat_November_2010-1a.jpg/960px-Cat_November_2010-1a.jpg",
        {"text": "Explain this meme", "image": "proof_of_concept/ollama_turbo/images/image.png"},
        # Individual (per-request params => not batched)
        {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Tell me a short joke."}
            ],
            "temperature": 0.7
        }
    ]
    return await litellm_call(prompts[0:5], wrap_json=False)


def demo_sync() -> List[str]:
    return asyncio.run(demo())


if __name__ == "__main__":
    import typer  # Typer is a declared dependency; import directly

    cli = typer.Typer(
        name="litellm_call",
        help=(
            "Thin async batch runner with image support via LiteLLM Router.\n\n"
            "Examples:\n"
            "  - Single: python litellm_call.py \"What is 2+2?\"\n"
            "  - Batch:  python litellm_call.py \"What is 2+2?\" \"Capital of France?\"\n"
            "  - Images: python litellm_call.py \"Describe /path/to/image.jpg and https://example.com/cat.jpg\"\n"
            "  - Files:  python litellm_call.py @prompts.txt   | @prompts.jsonl | prompts.json\n"
            "  - Stdin:  echo \"What is 2+2?\" | python litellm_call.py --stdin\n"
        ),
    )

    @cli.command()
    def main(
        sources: List[str] = typer.Argument(None, help="Prompts or files containing prompts. Use @file to read a file, or '-' for stdin."),
        model: str = typer.Option(MODEL, "--model", "-m", help="Default LiteLLM model name"),
        models: Optional[str] = typer.Option(None, "--models", help="Comma-separated list of models for 'one prompt → many models'"),
        stdin: bool = typer.Option(False, "--stdin", help="Read prompts from stdin"),
        jsonl: bool = typer.Option(False, "--jsonl", help="Input is in JSON Lines format"),
        wrap_json: bool = typer.Option(False, "--wrap-json", help="Wrap non-JSON outputs in JSON and add usage/cost in metadata"),
        max_parallel: int = typer.Option(DEFAULT_MAX_PARALLEL or 0, "--max-parallel", help="Router default_max_parallel_requests (0 = unset)"),
        num_retries: int = typer.Option(DEFAULT_NUM_RETRIES, "--num-retries", help="Router num_retries"),
        response_format: Optional[str] = typer.Option(None, "--response-format", help="Inject response_format type (e.g., 'json_object')"),
        request_timeout: Optional[float] = typer.Option(None, "--timeout", help="Request timeout in seconds"),
        stream: bool = typer.Option(False, "--stream", help="Stream output for a single prompt"),
        image_cache_dir: Optional[str] = typer.Option(None, "--image-cache-dir", help="Directory for persistent image cache (overrides LITELLM_IMAGE_CACHE_DIR)"),
    ):
        # Apply defaults
        global MODEL
        if model:
            MODEL = model

        # NOTE: Auth is handled via environment and load_dotenv(find_dotenv()).
        # No API key/base mutation here; keep this thin and defer to LiteLLM env parsing.

        # Optional image cache dir override
        global _IMAGE_CACHE_DIR
        if image_cache_dir:
            _IMAGE_CACHE_DIR = image_cache_dir

        # Build the prompt list from args/stdin/files
        prompts: List[object] = []
        from pathlib import Path as _Path

        if stdin or (sources == ["-"]):
            for line in sys.stdin:
                line = line.rstrip("\n")
                if jsonl:
                    prompts.append(json.loads(line))
                else:
                    prompts.append(line)

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
                prompts.extend(json.loads(l) for l in path.read_text().splitlines() if l.strip())
            else:
                prompts.extend(path.read_text().splitlines())

        if not prompts:
            typer.echo("No prompts provided.", err=True)
            raise typer.Exit(1)

        dmpr = max_parallel if max_parallel and max_parallel > 0 else None
        model_list_opt = [m.strip() for m in models.split(",")] if models else None
        results = asyncio.run(
            litellm_call(
                prompts,
                wrap_json=wrap_json,
                default_max_parallel_requests=dmpr,
                num_retries=num_retries,
                response_format=response_format,
                request_timeout=request_timeout,
                stream=stream,
                models=model_list_opt,
            )
        )
        for r in results:
            typer.echo(r)

    @cli.command("sanity")
    def sanity(
        model: str = typer.Option(MODEL, "--model", "-m", help="Model to use for the sanity check"),
        wrap_json: bool = typer.Option(False, "--wrap-json", help="Wrap non-JSON and include error/usage metadata"),
        request_timeout: Optional[float] = typer.Option(None, "--timeout", help="Request timeout in seconds"),
    ):
        """Quick sanity check via LiteLLM Router.

        Prints the model's JSON response and exits 0 only if the parsed JSON contains {"ok": true}.
        This tolerates additional fields like metadata injected by the adapter.
        """
        global MODEL
        if model:
            MODEL = model

        prompt = 'Return only {"ok":true} as JSON.'
        results = asyncio.run(
            litellm_call(
                [prompt],
                wrap_json=wrap_json,
                response_format="json_object",
                request_timeout=request_timeout,
            )
        )
        out = results[0] if results else ""
        typer.echo(out)

        ok = False
        try:
            data = json.loads(out.strip())
            if isinstance(data, dict):
                if data.get("ok") is True:
                    ok = True
                else:
                    content = data.get("content")
                    if isinstance(content, dict) and content.get("ok") is True:
                        ok = True
        except Exception:
            ok = False

        raise typer.Exit(code=0 if ok else 2)

    cli()
