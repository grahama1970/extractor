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


app = typer.Typer(add_completion=False, help="Smoke: litellm_call sanitization modes for data URLs")

TINY_PNG_DATA = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _ensure_paths():
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / "src"))
    (root / "scripts" / "artifacts").mkdir(parents=True, exist_ok=True)
    return root


def _artifact_path(root: Path, label: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return root / "scripts" / "artifacts" / f"call2_sanitize_{label}_{ts}.json"


def _make_prompt_with_data_url() -> dict:
    data_url = f"data:image/png;base64,{TINY_PNG_DATA}"
    return {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this inline image."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ]
    }


@app.command()
def run(
    mode: str = typer.Option("redact", "--mode", help="redact|hash|truncate|none"),
    chars: int = typer.Option(48, "--chars", help="used for truncate"),
    model: str | None = typer.Option(None, "--model", "-m"),
):
    """Run a single sanitization mode and save the sanitized request in artifacts."""
    try:
        load_dotenv(find_dotenv(usecwd=True) or None)
        os.environ.setdefault("LITELLM_HTTPX", "1")
        root = _ensure_paths()
        from extractor.pipeline.utils import litellm_call as call2  # type: ignore

        prompt = _make_prompt_with_data_url()
        results = call2.asyncio.run(  # type: ignore[attr-defined]
            call2.litellm_call(
                [prompt],
                default_model=(model or call2.DEFAULT_MODEL),
                wrap_json=False,
                request_timeout=15,
                num_retries=0,
                show_progress=False,
                concurrency=1,
                sanitize_data_urls=mode,
                sanitize_truncate_chars=chars,
                export="results",
            )
        )
        r = results[0]
        out = {
            "mode": mode,
            "chars": chars,
            "request_messages": r.request.messages,
            "content_head": (r.content or "")[:120],
        }
        path = _artifact_path(root, mode)
        path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        typer.echo(f"OK: saved {path}")
    except Exception as e:
        typer.echo(f"Smoke error: {e}", err=True)
        raise SystemExit(1)


@app.command()
def all(model: str | None = typer.Option(None, "--model", "-m")):
    """Run all modes in sequence and save artifacts for each."""
    for mode in ("redact", "hash", "truncate", "none"):
        code = os.system(
            f"{sys.executable} {Path(__file__).resolve()} run --mode {mode} --chars 48"
            + (f" -m '{model}'" if model else "")
        )
        if code != 0:
            raise SystemExit(1)


if __name__ == "__main__":
    app()
