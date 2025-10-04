#!/usr/bin/env python3
"""
Minimal Litellm vision sanity check with a tiny in-memory PNG and a short prompt.

Prereqs:
- GEMINI_API_KEY (or GOOGLE_API_KEY)
- LITELLM_VLM_MODEL or LITELLM_DEFAULT_MODEL pointing to a Gemini vision-capable model

Run:
  source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a
  PYTHONPATH=src python debug/test_litellm_gemini_vision.py
"""
from __future__ import annotations

import base64
import io
import os
import sys
from typing import Any

try:
    from PIL import Image, ImageDraw
except Exception as e:
    print(f"Pillow not installed: {e}", file=sys.stderr)
    sys.exit(2)

try:
    import litellm
except Exception as e:
    print(f"Litellm import failed: {e}", file=sys.stderr)
    sys.exit(2)


def env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def tiny_png_b64() -> str:
    img = Image.new("RGB", (32, 32), color=(200, 50, 50))
    d = ImageDraw.Draw(img)
    d.rectangle([8, 8, 24, 24], outline=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def main() -> int:
    model = env("LITELLM_VLM_MODEL") or env("LITELLM_DEFAULT_MODEL")
    if not model:
        print("Set LITELLM_VLM_MODEL or LITELLM_DEFAULT_MODEL to a Gemini vision model.", file=sys.stderr)
        return 3
    if not (env("GEMINI_API_KEY") or env("GOOGLE_API_KEY")):
        print("Set GEMINI_API_KEY or GOOGLE_API_KEY.", file=sys.stderr)
        return 4
    print(f"Using model: {model}")

    b64 = tiny_png_b64()
    user_content = [
        {"type": "text", "text": "Describe the red square image in one sentence."},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    ]
    try:
        resp: Any = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": "You are a concise computer vision assistant."},
                {"role": "user", "content": user_content},
            ],
            timeout=60,
        )
        content = resp["choices"][0]["message"]["content"]
        print("Vision response:\n", content)
        return 0
    except Exception as e:
        print("Vision call error:", e, file=sys.stderr)
        return 10


if __name__ == "__main__":
    sys.exit(main())

