#!/usr/bin/env python3
"""
Quick Litellm sanity check against Gemini using environment configuration.

Requires:
- GEMINI_API_KEY (or GOOGLE_API_KEY) set in the environment
- LITELLM_DEFAULT_MODEL or LITELLM_VLM_MODEL pointing to a Gemini model

Usage:
  source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a
  python debug/test_litellm_gemini.py
"""
from __future__ import annotations

import os
import sys
import json
from typing import Any

try:
    import litellm
except Exception as e:
    print(f"Litellm not installed or import failed: {e}", file=sys.stderr)
    sys.exit(2)


def env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def main() -> int:
    gemini_key = env("GEMINI_API_KEY") or env("GOOGLE_API_KEY")
    if not gemini_key:
        print("GEMINI_API_KEY/GOOGLE_API_KEY is not set.", file=sys.stderr)
        return 3

    model = env("LITELLM_DEFAULT_MODEL") or env("DEFAULT_LITELLM_MODEL") or env("LITELLM_VLM_MODEL")
    if not model:
        print(
            "No LLM model set (LITELLM_DEFAULT_MODEL/DEFAULT_LITELLM_MODEL/LITELLM_VLM_MODEL)",
            file=sys.stderr,
        )
        return 4

    print(f"Using model: {model}")
    try:
        resp: Any = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": 'Return only the JSON {"ok": true}.'},
            ],
            timeout=30,
            # For providers supporting response_format, litellm will adapt as needed
            # response_format={"type": "json_object"},
        )
        # litellm returns a dict-like structure similar to OpenAI format
        try:
            content = resp["choices"][0]["message"]["content"]
        except Exception:
            content = str(resp)
        print("Raw content:\n", content)
        # Try to parse to confirm connectivity
        try:
            data = json.loads(content)
            print("Parsed JSON:", data)
            if isinstance(data, dict) and data.get("ok") is True:
                print("OK: Litellm Gemini call succeeded.")
                return 0
        except Exception:
            pass
        print("NOTE: Response was not strict JSON; connectivity still verified.")
        return 0
    except litellm.RateLimitError as e:  # type: ignore[attr-defined]
        print("RateLimitError:", e, file=sys.stderr)
        return 10
    except litellm.Timeout as e:  # type: ignore[attr-defined]
        print("Timeout:", e, file=sys.stderr)
        return 11
    except Exception as e:
        print("LLM call error:", e, file=sys.stderr)
        return 12


if __name__ == "__main__":
    sys.exit(main())
