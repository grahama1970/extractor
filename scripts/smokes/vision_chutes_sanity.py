#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12.3",
# ]
# ///

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional
import urllib.request

import typer
from dotenv import load_dotenv, find_dotenv

ART = Path(__file__).resolve().parents[1] / "artifacts"
ART.mkdir(parents=True, exist_ok=True)


def _http_request(method: str, url: str, api_key: str, payload: dict | None = None, timeout: float = 20.0) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method.upper(), headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_chat_completion(api_base: str, api_key: str, payload: dict, timeout: float = 20.0) -> dict:
    req = urllib.request.Request(
        f"{api_base.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _vision_needles() -> list[str]:
    return [
        "gpt-4o", "omni", "vision", "vl", "glm-4v", "qwen-vl", "qwen3-vl", "pixtral", "mistral-vl", "llava", "minicpm-v",
    ]


def _is_vision_id(model_id: str) -> bool:
    low = str(model_id).lower()
    return any(n in low for n in _vision_needles())


def _pick_vision_model(models_obj: dict) -> Optional[str]:
    ids = [x.get("id") for x in (models_obj.get("data") or []) if isinstance(x, dict) and x.get("id")]
    if not ids:
        return None
    for m in ids:
        if _is_vision_id(str(m)):
            return str(m)
    return None


def _run(model: Optional[str], image_url: str, api_base: str, api_key: str, timeout: float = 20.0) -> tuple[bool, str]:
    # Probe models; auto-pick a vision-capable model if not provided
    models_obj = _http_request("GET", f"{api_base.rstrip('/')}/models", api_key, None, timeout)
    mdl = model if (model and _is_vision_id(model)) else _pick_vision_model(models_obj)
    if not mdl:
        return False, "<no vision-capable model detected>"
    msgs = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Return only {\"ok\":true,\"desc\":string} as JSON."},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }
    ]
    payload = {
        "model": mdl,
        "messages": msgs,
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    # Try chat.completions; if 404, try responses
    try:
        data = _http_chat_completion(api_base, api_key, payload, timeout=timeout)
    except Exception as e:
        # Fallback to Responses API shape
        payload_resp = {
            "model": mdl,
            "response_format": {"type": "json_object"},
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": 'Return only {"ok": true, "desc": string} as JSON.'},
                        {"type": "input_image", "image_url": image_url},
                    ],
                }
            ],
        }
        data = _http_request("POST", f"{api_base.rstrip('/')}/responses", api_key, payload_resp, timeout)
    content = (((data or {}).get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    try:
        obj = json.loads((content or "").strip())
        ok = isinstance(obj, dict) and obj.get("ok") is True and isinstance(obj.get("desc"), str)
        return ok, content
    except Exception:
        return False, content


def main(
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    image_url: str = typer.Option(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/Grosser_Panda.JPG/960px-Grosser_Panda.JPG",
        "--image",
    ),
):
    # Load .env so we always pick up CHUTES/OPENAI keys without exporting
    try:
        load_dotenv(find_dotenv(usecwd=True) or None)
    except Exception:
        pass
    base = os.getenv("CHUTES_API_BASE") or os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE")
    key = os.getenv("CHUTES_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not base or not key:
        typer.echo("SKIP: Missing CHUTES/OPENAI base+key; set creds then rerun.")
        raise typer.Exit(code=0)

    mdl = model or os.getenv("CHUTES_MODEL")
    ok, content = _run(mdl, image_url, base, key)
    tag = "pass" if ok else "fail"
    out = ART / f"vision_chutes_{tag}.json"
    out.write_text(json.dumps({"ok": ok, "model": mdl, "image": image_url, "content": content}, indent=2), encoding="utf-8")
    typer.echo(str(out))
    raise typer.Exit(code=0 if ok else 3)


if __name__ == "__main__":
    typer.run(main)
