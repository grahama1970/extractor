#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "litellm>=1.74.7",
#   "tqdm",
#   "loguru",
#   "pillow",
#   "httpx",
#   "json-repair",
#   "urlextract",
#   "strip-tags",
#   "numpy",
#   "pandas",
# ]
# ///
"""
Smoke: Minimal Stage 07 reflow via litellm_call (results mode)

Focuses on the historical empty-results issue by sending a compact prompt
with one small, stable image and asserting non-empty content.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: Stage 07 reflow minimal (litellm_call)")


def _ensure_paths():
    """Establish project root, source path, and artifacts directory."""
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / "src"))
    (root / "scripts" / "artifacts").mkdir(parents=True, exist_ok=True)
    return root


def _artifact_path(root: Path) -> Path:
    """Perform artifact path operation."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return root / "scripts" / "artifacts" / f"stage07_reflow_min_{ts}.json"


def _resolve_model() -> str:
    # Prefer SMOKE_MODEL, else OpenAI default if key detected, else VLM/DEFAULT chain
    sm = os.getenv("SMOKE_MODEL", "").strip()
    if sm:
        return sm
    if os.getenv("OPENAI_API_KEY"):
        return "openai/gpt-4o-mini"
    return (
        os.getenv("LITELLM_VLM_MODEL")
        or os.getenv("LITELLM_DEFAULT_MODEL")
        or os.getenv("DEFAULT_LITELLM_MODEL")
        or os.getenv("LITELLM_MODEL")
        or "gemini/gemini-2.5-flash"
    )


def run_smoke(timeout: int, model: str) -> None:
    """Run smoke tests with specified timeout and model parameters."""
    try:
        load_dotenv(find_dotenv(usecwd=True) or None)
        os.environ.setdefault("LITELLM_HTTPX", "1")
        root = _ensure_paths()
        from extractor.pipeline.utils import litellm_call as call2  # type: ignore
        from extractor.pipeline.utils.image_helpers import compress_image_cached  # type: ignore

        # Build a tiny, stable data URL for the image
        img_path = Path("tests/stage07_manual/images/smoke/panda.png")
        data_url = None
        if img_path.exists():
            data_url = compress_image_cached(str(img_path), max_kb=200)
        else:
            # Fallback small remote PNG
            data_url = "https://httpbin.org/image/png"

        guard = (
            "You are a strict JSON reflow engine. Return ONLY JSON: "
            '{"reflowed_json":{"blocks":[{"type":"paragraph","text":string}]},'  # minimal sketch
            '"ocr_corrections":{},"improvements_made":string}. '
            'If not possible, return {"reflowed_text":string}. No code fences.'
        )
        context = "Section: Minimal test section."

        # Compose messages with image part
        is_gemini = "gemini" in (model or "").lower()
        img_part = {"type": "image_url", "image_url": {"url": data_url}} if data_url else None
        if is_gemini:
            parts = [{"type": "text", "text": f"{guard}\n\n{context}"}]
            if img_part:
                parts.append(img_part)
            messages = [{"role": "user", "content": parts}]
        else:
            parts = [{"type": "text", "text": context}]
            if img_part:
                parts.append(img_part)
            messages = [
                {"role": "system", "content": guard},
                {"role": "user", "content": parts},
            ]

        params = {
            "model": model,
            "messages": messages,
            "timeout": timeout,
        }

        results = call2.asyncio.run(  # type: ignore[attr-defined]
            call2.litellm_call(
                [params],
                wrap_json=False,
                concurrency=1,
                desc="reflow_min",
                session_id=os.getenv("LITELLM_SESSION_ID") or "smoke-07-min",
                sanitize_data_urls="redact",
                sanitize_truncate_chars=48,
                export="results",
            )
        )
        r0 = results[0] if results else None
        ok = bool(r0 and isinstance(r0.content, str) and r0.content.strip())
        artifact = {
            "ok": ok,
            "model": model,
            "request": {
                "model": getattr(getattr(r0, "request", object()), "model", None),
                "messages": getattr(getattr(r0, "request", object()), "messages", None),
                "kwargs": getattr(getattr(r0, "request", object()), "kwargs", None),
            },
            "content_head": (getattr(r0, "content", "") or "")[:240],
            "error": (
                None
                if getattr(r0, "exception", None) is None
                else str(getattr(r0, "exception", None))
            ),
        }
        out = _artifact_path(root)
        out.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        if ok:
            typer.echo(f"OK: stage07 minimal reflow returned content; artifact: {out}")
        else:
            typer.echo(f"Smoke failed: empty content; artifact: {out}", err=True)
            raise SystemExit(1)
    except Exception as e:
        typer.echo(f"Smoke error: {e}", err=True)
        raise SystemExit(1)


@app.command()
def main(
    timeout: int = typer.Option(45, help="Request timeout seconds"),
    model: str = typer.Option(_resolve_model(), help="Model to use"),
):
    """Run the smoke test with specified timeout and model."""
    run_smoke(timeout, model)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        app()
    else:
        run_smoke(45, _resolve_model())
