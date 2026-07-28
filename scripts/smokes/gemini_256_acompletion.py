#!/usr/bin/env python3
"""
Smoke: LiteLLM Router.acompletion with Gemini (256x256 image)

- Generates a 256x256 PNG in-memory (solid color)
- Sends a simple multimodal prompt to gemini/gemini-2.5-flash
- Prints a compact JSON report and saves artifacts under scripts/artifacts/

Usage:
  source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a
  python scripts/smokes/gemini_256_acompletion.py
"""
import asyncio
import base64
import io
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from litellm import Router


def png_256x256_base64(color=(255, 255, 255, 255)) -> str:
    """Return a base64-encoded PNG image of specified color."""
    from PIL import Image

    img = Image.new("RGBA", (256, 256), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


async def run_smoke() -> dict:
    """Run a smoke test on the LiteLLM router configuration."""
    load_dotenv(find_dotenv())

    model = os.getenv("LITELLM_DEFAULT_MODEL", "gemini/gemini-2.5-flash")
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    router = Router(
        model_list=[
            {
                "model_name": "gemini-flash",
                "litellm_params": {
                    "model": model,
                    **({"api_key": api_key} if api_key else {}),
                },
            }
        ]
    )

    b64 = png_256x256_base64((240, 240, 240, 255))
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Return only a brief description of this image."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        }
    ]

    report = {
        "model": model,
        "ok": False,
        "error": None,
        "response": None,
    }
    try:
        resp = await router.acompletion(model="gemini-flash", messages=messages, timeout=45)
        # Minimal extraction; exact structure varies by provider
        report["response"] = str(resp)
        report["ok"] = True
    except Exception as e:
        report["error"] = str(e)
    return report


def main() -> int:
    """Run smoke test and save report as JSON artifact."""
    out_dir = Path("scripts/artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)
    report = asyncio.run(run_smoke())
    ts = datetime.utcnow().isoformat().replace(":", "-").replace(".", "-")
    out_path = out_dir / f"gemini_256_acompletion_{ts}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"artifact: {out_path}")
    if report.get("ok"):
        print("gemini_256_acompletion: OK")
        return 0
    else:
        print("gemini_256_acompletion: FAIL", report.get("error") or "unknown")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
