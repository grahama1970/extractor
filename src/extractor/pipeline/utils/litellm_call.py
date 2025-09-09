#!/usr/bin/env python3

"""
LiteLLM Call - Easy async LLM batch runner with automatic image support

WHAT IT DOES:
- Run multiple LLM prompts in parallel for speed
- Automatically detects and includes images from URLs or local files
- Works with any LiteLLM-supported model (OpenAI, Anthropic, Ollama, etc.)
- Handles all image processing automatically (compression, base64 encoding)

WHAT THIS SCRIPT DOES **NOT** DO:
- It does NOT inject JSON mode, system prompts, schemas, or tool-call definitions.  
  If you need strict JSON, include `"response_format": {"type": "json_object"}`  
  (or a system prompt) yourself.  
- It does NOT support or transform tool calls; pass a full LiteLLM dict with `tools` if required.

QUICK START:
1. Basic text prompt:
   $ python litellm_call.py "What is 2+2?"

2. Multiple prompts (run in parallel):
   $ python litellm_call.py "What is 2+2?" "What is the capital of France?"

3. Prompt with images (auto-detected):
   $ python litellm_call.py "What's in this image? /path/to/image.jpg"
   $ python litellm_call.py "Compare: https://example.com/cat.jpg and dog.png"

4. From files:
   $ python litellm_call.py @prompts.txt        # One prompt per line
   $ python litellm_call.py prompts.json        # JSON array of prompts
   $ python litellm_call.py @prompts.jsonl      # JSON Lines format
   
5. From stdin:
   $ echo "What is 2+2?" | python litellm_call.py --stdin
   $ cat prompts.jsonl | python litellm_call.py --stdin --jsonl

ENVIRONMENT SETUP:
- OLLAMA_DEFAULT_MODEL: Model to use (default: "ollama/gemma3:12b")
- OLLAMA_BASE_URL: API endpoint (default: "http://localhost:11434")
- OLLAMA_API_KEY: API key if required

ADVANCED USAGE:
- Override model: --model "gpt-4"
- Custom API: --api-base "https://api.openai.com/v1"
- With API key: --api-key "sk-..."

INPUT FORMATS:
1. Simple string: "What is 2+2?"
2. With image: {"text": "Explain this", "image": "path/to/image.jpg"}
3. Full control: {"model": "gpt-4", "messages": [...], "temperature": 0.7}

FEATURES:
- Automatic image detection in prompts (URLs and file paths)
- Smart image compression to stay under API limits
- Parallel processing with progress bar
- Automatic retries on failures
- Silent handling of missing/broken images
- Supports all common image formats (jpg, png, gif, etc.)

"""
import asyncio
import sys
import json
import base64
import io
import os
import re
from pathlib import Path
from typing import List, Tuple, Any, Dict
from copy import deepcopy

import httpx
from PIL import Image
from litellm import acompletion
import litellm as _litellm
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm.asyncio import tqdm
from loguru import logger
from dotenv import load_dotenv, find_dotenv
from urlextract import URLExtract
try:
    import typer
    _HAS_TYPER = True
except Exception:
    _HAS_TYPER = False
    class _TyperShim:
        def __init__(self,*a,**k): pass
        def command(self,*a,**k): return lambda f: f
        def __call__(self,*a,**k): print("Typer not installed; CLI disabled")
    def _opt(*a,**k): return None
    def _arg(*a,**k): return None
    typer = _TyperShim()  # type: ignore
    typer.Typer = _TyperShim  # type: ignore
    typer.Option = _opt  # type: ignore
    typer.Argument = _arg  # type: ignore
    typer.secho = print  # type: ignore

from strip_tags import strip_tags

logger.remove()
logger.add(sys.stderr, level="WARNING")
from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache


load_dotenv(find_dotenv())
_litellm.drop_params = True  # tolerate provider-specific unsupported params
initialize_litellm_cache()

# -----------------------------------------------------------------------------
#  Typer app  (NEW)
# -----------------------------------------------------------------------------
# Typer app is defined only when executed as a script

# Default model configuration - works with any LiteLLM provider
MODEL = os.getenv("LITELLM_MODEL", os.getenv("OLLAMA_DEFAULT_MODEL", "ollama/gemma3:12b"))

# Provider-specific configurations (LiteLLM will use the appropriate ones)
# For Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")

# For Moonshot/Kimi
MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY", "")
MOONSHOT_API_BASE = os.getenv("MOONSHOT_API_BASE", "https://api.moonshot.ai/v1")

# For OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# For Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"}
extractor = URLExtract()

SHOW_PROGRESS = os.getenv("LITELLM_NO_PROGRESS", "").lower() not in {"1", "true", "yes"}

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def safe_image(path: Path) -> bool:
    """True if file exists, has an image extension, and PIL can open it."""
    try:
        return path.exists() and path.suffix.lower() in IMAGE_EXT and Image.open(path).verify() is None
    except Exception:
        return False


def extract_images(text: str) -> tuple[List[str], str]:
    """
    Return:
        - list[str] of all valid image URLs/paths (remote & local)
        - cleaned prompt text with placeholders {Image 1}, {Image 2}, …
    """
    found, seen = [], set()

    # 1) Strip XML/HTML tags ----------------------------------------------------
    plain = strip_tags(text)

    # 2) Remote URLs -----------------------------------------------------------
    for url in extractor.find_urls(plain):
        url = url.strip()
        if url.lower().endswith(tuple(IMAGE_EXT)) and url not in seen:
            found.append(url)
            seen.add(url)

    # 3) Local files -----------------------------------------------------------
    tokens = re.findall(r'(?:"[^"]*"|\'[^\']*\'|\S+)', plain)
    for tok in tokens:
        tok = tok.strip('"\'')
        if not tok:
            continue
        candidate = Path(tok).expanduser().resolve()
        if safe_image(candidate) and str(candidate) not in seen:
            found.append(str(candidate))
            seen.add(str(candidate))

    # 4) Build cleaned prompt with placeholders --------------------------------
    cleaned = text
    for idx, img in enumerate(found, 1):
        placeholder = f"{{Image {idx}}}"
        cleaned = cleaned.replace(img, placeholder)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

    return found, cleaned


def compress_image(path_str: str, max_kb: int = 1000) -> str:
    """Return base-64 data-URI for a *local* image, compressed if required."""
    path = Path(path_str)
    img_bytes = path.read_bytes()
    max_bytes = max_kb * 1024

    if len(img_bytes) <= max_bytes:
        mime = f"image/{path.suffix[1:]}"
        return f"data:{mime};base64,{base64.b64encode(img_bytes).decode()}"

    img = Image.open(io.BytesIO(img_bytes))
    quality = 85
    while quality > 20:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if len(buf.getvalue()) <= max_bytes:
            return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"
        quality -= 10

    img.thumbnail((img.width // 2, img.height // 2))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=30)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"


def fetch_remote_image(url: str) -> str | None:
    """Download remote image and return base-64 data-URI or None on failure."""
    try:
        r = httpx.get(url, timeout=10)
        r.raise_for_status()
        mime = r.headers.get("content-type", "image/jpeg").split(";")[0]
        return f"data:{mime};base64,{base64.b64encode(r.content).decode()}"
    except Exception as e:
        logger.warning(f"Skipping remote image {url}: {e}")
        return None


# -----------------------------------------------------------------------------
# LITELLM UTILITIES
# -----------------------------------------------------------------------------

# Note: we don't need this
def _build_params(model: str,
                  messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return the final dict for acompletion, injecting only needed keys."""
    params = {"model": model, "messages": messages}

    # LiteLLM auto-detects most providers, but Ollama needs an explicit base URL
    if model.startswith("ollama/"):
        # Special case for large models hosted on ollama.com
        if "120b" in model or "gpt-oss" in model:
            params["api_base"] = "https://ollama.com"
            if OLLAMA_API_KEY:
                params["api_key"] = OLLAMA_API_KEY
        else:
            # Regular local ollama models
            params["api_base"] = OLLAMA_BASE_URL
            if OLLAMA_API_KEY:
                params["api_key"] = OLLAMA_API_KEY

    return params

# -----------------------------------------------------------------------------
# Cost and token-usage helpers
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

    # Return compact JSON string for arrays/scalars
    return json.dumps(parsed, ensure_ascii=False)

# -----------------------------------------------------------------------------
# LLM call with retry
# -----------------------------------------------------------------------------

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
async def _call(params: Dict[str, Any], idx: int) -> Tuple[int, Any]:
    """Call LiteLLM and always return (idx, result_or_exception).

    This prevents task-level exceptions from bubbling out of as_completed,
    so callers can record a structured error per prompt without crashing.
    """
    try:
        resp = await acompletion(**params)
        return idx, resp
    except Exception as e:
        # Map provider errors to clearer ValueError when images are present but model lacks vision
        try:
            msgs = params.get("messages") or []
            # Detect any image_url content parts in messages
            def _has_image(ms):
                for m in ms:
                    content = m.get("content")
                    if isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "image_url":
                                return True
                return False
            if _has_image(msgs):
                m = str(e).lower()
                if any(kw in m for kw in ["does not support", "unsupported", "image input", "image_url", "no vision", "vision not", "invalid type for", "doesn't support"]):
                    model = params.get("model", "unknown")
                    return idx, ValueError(f"Model '{model}' does not support image inputs: {e}")
        except Exception:
            pass
        return idx, e


# -----------------------------------------------------------------------------
# Batch runner
# -----------------------------------------------------------------------------

async def litellm_call(
    prompts: List[Any],
    *,
    wrap_json: bool = False,
    concurrency: int | None = None,
    desc: str | None = None,
) -> List[str]:
    """
    Run any combination of prompts in parallel.

    Accepts:
        - plain strings
        - shorthand dicts: {"text": "...", "image": "...", "model": "..."}
        - full LiteLLM dicts: {"model": "...", "messages": [...], "api_base": "..."}

    Returns:
        List of text answers in the same order as the input list.
    """
    # Normalize single prompt → list
    if isinstance(prompts, (str, dict)):
        prompts = [prompts]

    tasks: List[asyncio.Task[Tuple[int, Any]]] = []

    for idx, item in enumerate(prompts):
        # -----------------------------------------------------------
        # 1) Already a complete LiteLLM dict
        # -----------------------------------------------------------
        if isinstance(item, dict) and "messages" in item:
            item.setdefault("model", MODEL)  # add only if missing
            tasks.append(asyncio.create_task(_call(item, idx)))
            continue

        # -----------------------------------------------------------
        # 2) Shorthand dict or plain string with auto-image support
        # -----------------------------------------------------------
        if isinstance(item, dict):
            text   = str(item.get("text", ""))
            images = [str(item["image"])] if "image" in item else []
            model  = item.get("model", MODEL)
        else:
            images, text = extract_images(str(item))
            model = MODEL
            extra = {}

        content_parts = [{"type": "text", "text": text}]
        for img in images:
            url = fetch_remote_image(img) if img.startswith("http") else compress_image(img)
            if url:
                content_parts.append({"type": "image_url", "image_url": {"url": url}})

        params = {
            "model": model,
            "messages": [{"role": "user", "content": content_parts}]
        }
        if extra:
            params.update(extra)
        tasks.append(asyncio.create_task(_call(params, idx)))

    # -----------------------------------------------------------
    # Collect results in original order
    # -----------------------------------------------------------
    # Optional concurrency limiting: process tasks in batches
    total = len(tasks)
    results: List[str] = [""] * total

    if concurrency and concurrency > 0 and concurrency < total:
        # chunk indices
        for start in range(0, total, concurrency):
            chunk = tasks[start:start + concurrency]
            for coro in tqdm(
                asyncio.as_completed(chunk),
                total=len(chunk),
                desc=desc or "Processing",
                disable=not SHOW_PROGRESS
            ):
                idx, resp = await coro
                if isinstance(resp, Exception):
                    # Structured error output
                    if wrap_json:
                        final_answer = json.dumps({
                            "error": {
                                "type": type(resp).__name__,
                                "message": str(resp)[:400]
                            }
                        }, ensure_ascii=False)
                    else:
                        final_answer = ""
                    logger.warning(f"LiteLLM call failed for Q{idx}: {type(resp).__name__}: {resp}")
                else:
                    answer = resp.choices[0].message.content or ""
                    final_answer = _maybe_augment_json_with_cost(answer, resp, wrap_non_json=wrap_json)

                results[idx] = final_answer

                safe_prompt = deepcopy(prompts[idx])
                if isinstance(safe_prompt, dict) and "api_key" in safe_prompt:
                    safe_prompt["api_key"] = "***"
                logger.info(f"\nQ{idx}: {str(safe_prompt)[:50]}...\nA{idx}: {final_answer[:100]}...")
    else:
        for coro in tqdm(
            asyncio.as_completed(tasks),
            total=total,
            desc=desc or "Processing",
            disable=not SHOW_PROGRESS
        ):
            idx, resp = await coro
            if isinstance(resp, Exception):
                if wrap_json:
                    final_answer = json.dumps({
                        "error": {
                            "type": type(resp).__name__,
                            "message": str(resp)[:400]
                        }
                    }, ensure_ascii=False)
                else:
                    final_answer = ""
                logger.warning(f"LiteLLM call failed for Q{idx}: {type(resp).__name__}: {resp}")
            else:
                answer = resp.choices[0].message.content or ""
                final_answer = _maybe_augment_json_with_cost(answer, resp, wrap_non_json=wrap_json)

            results[idx] = final_answer

            safe_prompt = deepcopy(prompts[idx])
            if isinstance(safe_prompt, dict) and "api_key" in safe_prompt:
                safe_prompt["api_key"] = "***"
            logger.info(f"\nQ{idx}: {str(safe_prompt)[:50]}...\nA{idx}: {final_answer[:100]}...")

    return results


# NOTE: CLI bindings for this module are created only under
# `if __name__ == "__main__":` to avoid import-time side effects.
# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

async def demo() -> List[str]:
    """
    Run a canned set of prompts and return the results.
    Safe to call from other async code.
    """
    prompts = [
        "What is the capital of France?",
        "Calculate 15+27+38",
        "What is 3 + 5? Return JSON: {question:string,answer:number}",
        "What is this animal eating? proof_of_concept/ollama_turbo/images/image2.png",
        "Describe https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Labrador_Retriever_portrait.jpg/960px-Labrador_Retriever_portrait.jpg  and https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/Cat_November_2010-1a.jpg/960px-Cat_November_2010-1a.jpg",
        {"text": "Explain this meme", "image": "proof_of_concept/ollama_turbo/images/image.png"},
        {
            "model": "ollama/gpt-oss:120b",
            "api_base": "https://ollama.com",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Tell me a short joke."}
            ],
            "temperature": 1.0
        }
    ]


    return await litellm_call(prompts[2:3])


def demo_sync() -> List[str]:
    """
    Synchronous wrapper around `demo()` for callers that are not async.
    """
    return asyncio.run(demo())


if __name__ == "__main__":
    try:
        import typer as _ty
        cli = _ty.Typer(
            name="litellm_call",
            help="Fast async LLM batch runner with inline image support via LiteLLM / Ollama.",
        )

        @cli.command()
        def main(
            sources: list[str] = _ty.Argument(None, help="Prompts or files containing prompts"),
            model: str = _ty.Option(MODEL, "--model", "-m", help="LiteLLM model name"),
            api_base: str = _ty.Option(None, "--api-base", help="Override API base URL"),
            api_key: str = _ty.Option(None, "--api-key", help="Override API key"),
            stdin: bool = _ty.Option(False, "--stdin", help="Read prompts from stdin"),
            jsonl: bool = _ty.Option(False, "--jsonl", help="Input is in JSON Lines format"),
            wrap_json: bool = _ty.Option(False, "--wrap-json", help="Wrap non-JSON outputs in JSON"),
        ):
            # Reuse the same logic by calling the function below
            # Build prompts as in the original CLI
            prompts: list[object] = []
            from pathlib import Path as _Path
            import json as _json
            import sys as _sys

            global MODEL
            if model:
                MODEL = model
            if api_base:
                os.environ["OLLAMA_API_BASE"] = api_base
                os.environ["MOONSHOT_API_BASE"] = api_base
                os.environ["OPENAI_API_BASE"] = api_base
            if api_key:
                if model.startswith("ollama/"):
                    os.environ["OLLAMA_API_KEY"] = api_key
                elif model.startswith("moonshot/"):
                    os.environ["MOONSHOT_API_KEY"] = api_key
                elif model.startswith("gpt") or model.startswith("text-"):
                    os.environ["OPENAI_API_KEY"] = api_key
                elif model.startswith("claude"):
                    os.environ["ANTHROPIC_API_KEY"] = api_key

            if stdin or (sources == ["-"]):
                for line in _sys.stdin:
                    line = line.rstrip("\n")
                    if jsonl:
                        prompts.append(_json.loads(line))
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
                    prompts.extend(_json.loads(path.read_text()))
                elif path.suffix.lower() == ".jsonl" or jsonl:
                    prompts.extend(_json.loads(l) for l in path.read_text().splitlines() if l.strip())
                else:
                    prompts.extend(path.read_text().splitlines())

            if not prompts:
                _ty.echo("No prompts provided.", err=True)
                raise _ty.Exit(1)

            results = asyncio.run(litellm_call(prompts, wrap_json=wrap_json))
            for r in results:
                _ty.echo(r)

        cli()
    except Exception as _e:
        print("Typer CLI unavailable:", _e)
