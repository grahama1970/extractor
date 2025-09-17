#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List

import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: litellm_call basic runs + artifacts")


def _ensure_paths():
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / "src"))
    (root / "scripts" / "artifacts").mkdir(parents=True, exist_ok=True)
    return root


def _artifact_path(root: Path, label: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return root / "scripts" / "artifacts" / f"call2_{label}_{ts}.json"


def _write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


@app.command()
def sanity(
    prompt: str = typer.Argument('Return only {"ok":true} as JSON.'),
    model: str | None = typer.Option(None, "--model", "-m", help="Default model (falls back to .env)"),
    timeout: int = typer.Option(20, "--timeout"),
    wrap_json: bool = typer.Option(True, "--wrap-json"),
    sanitize_data_urls: str = typer.Option(
        "redact",
        "--sanitize-data-urls",
        help="Sanitize data URLs in returned request: 'redact' (default), 'hash', 'truncate', 'none'",
    ),
    sanitize_truncate_chars: int = typer.Option(48, "--sanitize-truncate-chars"),
):
    """Run a minimal sanity call via litelllm_call2 and save an artifact JSON."""
    try:
        load_dotenv(find_dotenv(usecwd=True) or None)
        os.environ.setdefault("LITELLM_HTTPX", "1")
        root = _ensure_paths()
        from extractor.pipeline.utils import litellm_call as call2  # type: ignore

        prompts: List[object] = [prompt]
        results = call2.asyncio.run(  # type: ignore[attr-defined]
            call2.litellm_call(
                prompts,
                default_model=(model or call2.DEFAULT_MODEL),
                wrap_json=wrap_json,
                response_format="json_object" if wrap_json else None,
                request_timeout=timeout,
                num_retries=0,
                show_progress=False,
                concurrency=1,
                sanitize_data_urls=sanitize_data_urls,
                sanitize_truncate_chars=sanitize_truncate_chars,
                export="results",
            )
        )
        # Save artifact with content + sanitized request summary
        artifact = [
            {
                "index": r.index,
                "content": r.content,
                "request": {
                    "model": r.request.model,
                    "messages": r.request.messages,
                    "kwargs": r.request.kwargs,
                },
                "ok": r.exception is None,
                "exception": None if r.exception is None else str(r.exception),
            }
            for r in results
        ]
        out = _artifact_path(root, "sanity")
        _write_json(out, artifact)
        typer.echo(f"OK: saved {out}")
    except Exception as e:
        typer.echo(f"Smoke error: {e}", err=True)
        raise SystemExit(1)


@app.command()
def image_url(
    url: str = typer.Argument(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/Grosser_Panda.JPG/960px-Grosser_Panda.JPG"
    ),
    model: str | None = typer.Option(None, "--model", "-m"),
    timeout: int = typer.Option(25, "--timeout"),
    sanitize_data_urls: str = typer.Option("redact", "--sanitize-data-urls"),
    sanitize_truncate_chars: int = typer.Option(48, "--sanitize-truncate-chars"),
):
    """Describe an image URL via litelllm_call2 and save an artifact JSON."""
    try:
        load_dotenv(find_dotenv(usecwd=True) or None)
        root = _ensure_paths()
        from extractor.pipeline.utils import litellm_call as call2  # type: ignore

        prompt = f"Describe this image: {url}"
        results = call2.asyncio.run(  # type: ignore[attr-defined]
            call2.litellm_call(
                [prompt],
                default_model=(model or call2.DEFAULT_MODEL),
                wrap_json=False,
                request_timeout=timeout,
                num_retries=0,
                show_progress=False,
                concurrency=1,
                sanitize_data_urls=sanitize_data_urls,
                sanitize_truncate_chars=sanitize_truncate_chars,
                export="results",
            )
        )
        artifact = [
            {
                "index": r.index,
                "content": r.content,
                "request": {
                    "model": r.request.model,
                    "messages": r.request.messages,
                    "kwargs": r.request.kwargs,
                },
                "ok": r.exception is None,
                "exception": None if r.exception is None else str(r.exception),
            }
            for r in results
        ]
        out = _artifact_path(root, "image")
        _write_json(out, artifact)
        typer.echo(f"OK: saved {out}")
    except Exception as e:
        typer.echo(f"Smoke error: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    app()
