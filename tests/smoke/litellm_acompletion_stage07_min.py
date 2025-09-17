#!/usr/bin/env python3
"""
Minimal Stage‑07 style smoke using Router.acompletion (Gemini).

Goal: Reproduce the core Stage‑07 call with one local image and the strict JSON
guard in the first user content item. No extra helpers, no remote fetches.

Usage (from repo root, with GEMINI_API_KEY in env):
  python tests/smoke/litellm_acompletion_stage07_min.py \
    --image tests/stage07_manual/images/smoke/panda.png \
    --compact
"""
import typer
import asyncio
import os
from pathlib import Path
import base64
import mimetypes
from typing import List, Any, Dict

from dotenv import load_dotenv, find_dotenv
from litellm import Router

from textwrap import dedent

# Optional project helpers; keep script runnable if unavailable
try:
    from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache  # type: ignore
except Exception:
    def initialize_litellm_cache() -> None:  # type: ignore
        return None

try:
    from extractor.pipeline.utils.litellm_image_utils import compress_image_cached  # type: ignore
except Exception:
    compress_image_cached = None  # type: ignore


def build_guard(compact: bool) -> str:
    if compact:
        return dedent(
            '''
            Return ONLY a JSON object (no code fences). Prefer this shape:
            {
              "reflowed_json": {
                "section_id": "string",
                "title": "string",
                "blocks": [ { "type": "paragraph", "text": "string" } ]
              },
              "ocr_corrections": {},
              "improvements_made": "string",
              "summary": "string"
            }
            If you cannot build reflowed_json, return { "reflowed_text": "string" } instead.
            '''
        ).strip()
    return dedent(
        '''
        You are a strict JSON reflow engine. Return ONLY a JSON object with keys:
        reflowed_json, ocr_corrections, improvements_made, summary. No code fences.
        Keep table cell text intact; include a figure block with caption when present.
        '''
    ).strip()


def _file_to_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def data_url_for_local(path: Path) -> str:
    """Return a data: URL for a local image, with a safe fallback.

    If project compressor is available, prefer it; otherwise, inline as base64.
    """
    if compress_image_cached is not None:
        try:
            out = compress_image_cached(str(path), max_kb=1000)
            if isinstance(out, str) and out.startswith("data:"):
                return out
        except Exception:
            pass
    return _file_to_data_url(path)


def build_messages(guard: str, context: str, image_data_urls: List[str]):
    # Stage‑07 Gemini shaping: guard in first user part (standard 'text' + multi image_url')
    content = [{"type": "text", "text": f"{guard}\n\n{context}"}]
    content.extend({"type": "image_url", "image_url": {"url": u}} for u in image_data_urls)
    return [{"role": "user", "content": content}]


def _extract_text(resp: Any) -> str:
    # Handle both dict-like and object-like LiteLLM responses
    if isinstance(resp, dict):
        ch = resp.get("choices") or []
        if not ch:
            return ""
        msg = ch[0].get("message") or {}
        return msg.get("content") or ""
    ch = getattr(resp, "choices", None) or []
    if not ch:
        return ""
    msg = getattr(ch[0], "message", None)
    return getattr(msg, "content", "") if msg is not None else ""


async def amain(images: List[Path], timeout: int, compact: bool, model: str, context: str) -> None:
    load_dotenv(find_dotenv())
    initialize_litellm_cache()
    os.environ.setdefault("LITELLM_LOG", "INFO")

    if not os.getenv("GEMINI_API_KEY"):
        typer.secho("GEMINI_API_KEY not set", fg="red", err=True)
        raise typer.Exit(code=2)

    router = Router(model_list=[{"model_name": model.split("/")[-1], "litellm_params": {"model": model, "api_key": os.getenv("GEMINI_API_KEY")}}])

    if not images:
        images = [Path("tests/stage07_manual/images/smoke/panda.png")]
    data_urls: List[str] = []
    for p in images:
        rp = p.resolve()
        if not rp.exists():
            typer.secho(f"Image not found: {rp}", fg="red", err=True)
            raise typer.Exit(code=2)
        data_urls.append(data_url_for_local(rp))
    guard = build_guard(compact)
    messages = build_messages(guard, context, data_urls)

    try:
        resp = await router.acompletion(model=model.split("/")[-1], messages=messages, timeout=timeout)
        # Print minimal surface: token usage and first content chunk
        usage = getattr(resp, "usage", None) if not isinstance(resp, dict) else resp.get("usage")
        print("usage:", usage)
        print("content:", _extract_text(resp))
    except Exception as e:
        typer.secho(f"ERROR: {repr(e)}", fg="red", err=True)
        raise typer.Exit(code=1)


app = typer.Typer(add_completion=False, help="Minimal Stage‑07 Gemini smoke (Typer CLI)")


@app.command()
def run(
    image: List[Path] = typer.Option([], "--image", "-i", help="Local image path(s) (PNG/JPG). Repeatable."),
    timeout: int = typer.Option(45, help="Request timeout (s)"),
    compact: bool = typer.Option(True, help="Use compact JSON guard"),
    model: str = typer.Option("gemini/gemini-2.5-flash", help="LiteLLM model id (e.g., gemini/gemini-2.5-flash)"),
    context: str = typer.Option(
        "Section: Example Submodule (level 2) pages 1–2\nParagraphs: raw text and one figure.",
        help="Minimal context text",
    ),
) -> None:
    """Run a Stage‑07‑style Gemini call (user guard + multi-image)."""
    asyncio.run(amain(images=image, timeout=timeout, compact=compact, model=model, context=context))


if __name__ == "__main__":
    app()
