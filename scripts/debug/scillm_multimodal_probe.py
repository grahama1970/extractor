#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12.3",
# ]
# ///
"""
Probe SciLLM multimodal (vision) via an OpenAI‑compatible gateway (e.g., Chutes).

Usage (env):
  export CHUTES_API_BASE=https://api.chutes.ai/v1
  export CHUTES_API_KEY=...
  uv run scripts/debug/scillm_multimodal_probe.py --image-url https://upload.wikimedia.org/wikipedia/commons/5/5f/Alaskan_Malamute.jpg

Notes
- If SciLLM is not installed into this venv, set SCILLM_PY_PATH to the repo path
  (e.g., /home/graham/workspace/experiments/litellm) and the script will add it to sys.path.
- Model ID: pass --model-id or let the script fetch /v1/models and pick the first VLM‑looking id.
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import typer
import urllib.request


def _add_scillm_path_from_env() -> None:
    p = os.getenv("SCILLM_PY_PATH")
    if p and Path(p).exists():
        sys.path.insert(0, p)


def _to_data_url(path: Path, max_kb: int = 256) -> str:
    # Minimal local image → data URL (JPEG). Prefer litellm.extras.images.compress_image if available.
    try:
        from litellm.extras.images import compress_image  # type: ignore

        return compress_image(str(path), max_kb=max_kb, cache_dir=".cache")
    except Exception:
        raw = path.read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:image/png;base64,{b64}"


def _pick_vlm_id(ids: list[str]) -> Optional[str]:
    prefers = ("vl", "vision", "gpt-4o", "qwen-vl", "kimi-vl")
    for i in ids:
        low = i.lower()
        if any(s in low for s in prefers):
            return i
    return ids[0] if ids else None


def _fetch_models(api_base: str, api_key: str, timeout: float = 15.0) -> list[str]:
    req = urllib.request.Request(
        api_base.rstrip("/") + "/models",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    return [x.get("id") for x in (data.get("data") or []) if x.get("id")]


def main(
    model_id: Optional[str] = typer.Option(None, "--model-id", help="Exact model id (from /v1/models)"),
    image_path: Optional[Path] = typer.Option(None, "--image-path", exists=True, file_okay=True, dir_okay=False),
    image_url: Optional[str] = typer.Option(None, "--image-url", help="HTTP(S) URL for an image"),
    prompt: str = typer.Option(
        'Describe the image in <= 8 words and return only {"ok":true,"desc":string} as JSON.',
        "--prompt",
        help="User text prompt",
    ),
    out: Path = typer.Option(Path("scripts/artifacts/scillm_vision_probe.json"), "--out", help="Save JSON here"),
):
    _add_scillm_path_from_env()

    api_base = os.getenv("CHUTES_API_BASE", "").rstrip("/")
    api_key = os.getenv("CHUTES_API_KEY", "")
    if not api_base or not api_key:
        typer.echo(json.dumps({"ok": False, "error": "CHUTES env not set"}))
        raise typer.Exit(2)

    try:
        from scillm import completion  # type: ignore
    except Exception as e:
        typer.echo(json.dumps({"ok": False, "error": f"import scillm failed: {e}"}))
        raise typer.Exit(3)

    # Resolve model id if not provided
    mid = model_id
    if not mid:
        try:
            ids = _fetch_models(api_base, api_key)
        except Exception as e:
            typer.echo(json.dumps({"ok": False, "error": f"models fetch failed: {e}"}))
            raise typer.Exit(4)
        mid = _pick_vlm_id(ids)
    if not mid:
        typer.echo(json.dumps({"ok": False, "error": "no model id found"}))
        raise typer.Exit(5)

    # Build message content with image part
    content: list[dict] = [{"type": "text", "text": prompt}]
    if image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url}})
    elif image_path:
        data_url = _to_data_url(image_path)
        content.append({"type": "image_url", "image_url": {"url": data_url}})
    else:
        # Default small Wikimedia image
        image_url = (
            "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Logo_OpenAI.svg/256px-Logo_OpenAI.svg.png"
        )
        content.append({"type": "image_url", "image_url": {"url": image_url}})

    # Call scillm (JSON mode; client-side strictness)
    resp = completion(
        model=mid,
        api_base=api_base,
        api_key=api_key,
        custom_llm_provider="openai",
        messages=[{"role": "user", "content": content}],
        response_format={"type": "json_object"},
        stop=["```", "END_JSON"],
        max_tokens=128,
    )

    content_str = resp.choices[0].message.get("content", "")
    # Try to parse; on failure emit raw string
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(content_str)
        data = {"ok": True, **data, "_model": mid}
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        typer.echo(json.dumps({"ok": True, "out": str(out), "model": mid}))
    except Exception:
        out.write_text(content_str, encoding="utf-8")
        typer.echo(json.dumps({"ok": False, "out": str(out), "model": mid, "note": "non-JSON content"}))


if __name__ == "__main__":
    raise SystemExit(typer.run(main))
