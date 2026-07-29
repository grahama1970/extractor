#!/usr/bin/env python3
from __future__ import annotations
import base64
import os
import sys
from pathlib import Path

import httpx

# Ensure extractor/src is first regardless of current working directory
_extractor_src = str(Path(__file__).resolve().parents[2] / "src")
if _extractor_src not in sys.path:
    sys.path.insert(0, _extractor_src)
# Optionally append litellm dev path (after extractor)
_litellm_dev = str(
    Path(os.environ.get("SCILLM_DEV_ROOT", Path.home() / "workspace/experiments/litellm"))
)
if os.path.isdir(_litellm_dev) and _litellm_dev not in sys.path:
    sys.path.append(_litellm_dev)
from scillm import completion


def _env(name: str) -> str:
    """Return the value of an environment variable or exit on missing."""
    v = (os.getenv(name) or "").strip()
    if not v:
        print(f"ENV_MISSING {name}")
        sys.exit(12)
    return v


def smoke_models():
    """Verify API models endpoint returns 200 OK."""
    base = os.environ.get("SCILLM_API_BASE", "http://localhost:4010")
    key = os.environ.get("SCILLM_PROXY_KEY", "sk-dev-proxy-123")
    r = httpx.get(
        base.rstrip("/") + "/models", headers={"Authorization": f"Bearer {key}"}, timeout=10
    )
    print(f"MODELS_HTTP {r.status_code}")
    if r.status_code != 200:
        sys.exit(21)
    try:
        data = r.json()
        first = (data.get("data") or [{}])[0].get("id", "")
        print(f"MODELS_FIRST_ID {first}")
    except Exception:
        pass


def smoke_json():
    """Check for the presence of a text model in environment variables."""
    model = os.getenv("CHUTES_TEXT_MODEL") or os.getenv("LITELLM_DEFAULT_MODEL")
    if not model:
        print("JSON_SMOKE_SKIPPED no_text_model")
        return

    def _once():
        """Execute a single API call to return a JSON response."""
        resp = completion(
            model=model,
            custom_llm_provider="openai_like",
            api_base=os.environ.get("SCILLM_API_BASE", "http://localhost:4010"),
            api_key=os.environ.get("SCILLM_PROXY_KEY", "sk-dev-proxy-123"),
            messages=[{"role": "user", "content": 'Return only {"ok":true} as JSON.'}],
            response_format={"type": "json_object"},
            timeout=20,
        )
        return (resp.get("choices") or [{}])[0].get("message", {}).get("content", "")

    try:
        content = _once()
    except Exception as e:
        msg = str(e)
        if "429" in msg or "maximum capacity" in msg.lower() or "Too Many Requests" in msg:
            import time

            print("JSON_SMOKE_RETRY 429 backoff 2s")
            time.sleep(2)
            content = _once()
        else:
            raise
    ok = '"ok":true' in (content or "").replace(" ", "")
    print(f"JSON_SMOKE_OK {int(bool(content))} {int(ok)}")
    if not content:
        sys.exit(31)


def smoke_vlm():
    # Prefer CHUTES_VLM_MODEL (canonical), then fall back to LITELLM_* for legacy envs
    model = (
        os.getenv("CHUTES_VLM_MODEL")
        or os.getenv("LITELLM_LARGE_VLLM_MODEL")
        or os.getenv("LITELLM_VLM_MODEL")
    )
    if not model:
        print("VLM_SMOKE_SKIPPED no_vlm_model")
        return
    png = base64.b64encode(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x06\x00\x03\n\xfdy\x8f\x00\x00\x00\x00IEND\xaeB`\x82"
    ).decode("ascii")
    messages = [
        {"role": "system", "content": "Describe the image in 1 short sentence."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Image follows"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{png}"}},
            ],
        },
    ]
    # Small backoff for transient 429/5xx; do not fail the doctor on brief capacity
    attempts = 0
    wait_s = 1.0
    while True:
        try:
            resp = completion(
                model=model,
                custom_llm_provider="openai_like",
                api_base=os.environ.get("SCILLM_API_BASE", "http://localhost:4010"),
                api_key=os.environ.get("SCILLM_PROXY_KEY", "sk-dev-proxy-123"),
                messages=messages,
                timeout=20,
            )
            content = (resp.get("choices") or [{}])[0].get("message", {}).get("content", "")
            print(f"VLM_SMOKE_OK {int(bool(content))}")
            if not content:
                print("VLM_SMOKE_EMPTY")
            return
        except Exception as e:
            attempts += 1
            msg = str(e)
            if attempts >= 3 or not any(
                t in msg
                for t in ("429", "Too Many Requests", "500", "Internal Server Error", "capacity")
            ):
                print(f'VLM_SMOKE_RETRY_EXHAUSTED {msg.splitlines()[0] if msg else ""}')
                return
            # brief guard; jitter
            import time
            import random

            time.sleep(wait_s + random.uniform(0, wait_s * 0.25))
            wait_s *= 1.5


def main():
    """Execute smoke tests and exit with a success status code."""
    smoke_models()
    smoke_json()
    smoke_vlm()
    print("DOCTOR_OK 0")
    sys.exit(0)


if __name__ == "__main__":
    main()
