#!/usr/bin/env python3
"""
Chutes Doctor (Minimal): Verifies the single pinned model returns JSON with 200.

Env:
- SCILLM_API_BASE, SCILLM_PROXY_KEY, CHUTES_TEXT_MODEL
"""
from __future__ import annotations
import os
import sys
import json
import asyncio

try:
    from litellm import Router
except Exception as e:
    print(f"missing litellm: {e}")
    sys.exit(2)


def env(name: str) -> str:
    """Return the value of an environment variable or exit on missing."""
    v = os.environ.get(name, "").strip()
    if not v:
        print(f"env missing: {name}")
        sys.exit(2)
    return v


base = os.environ.get("SCILLM_API_BASE", "http://localhost:4010")
key = os.environ.get("SCILLM_PROXY_KEY", "sk-dev-proxy-123")
mid = env("CHUTES_TEXT_MODEL")

model_list = [
    {
        "model_name": "chutes/text",
        "litellm_params": {
            "model": mid,
            "custom_llm_provider": "openai_like",
            "api_base": base,
            "api_key": None,
            "extra_headers": {"Authorization": f"Bearer {key}"},
        },
    }
]

router = Router(model_list=model_list, num_retries=0, default_litellm_params={"timeout": 20})


async def main() -> int:
    """Return a JSON response from an asynchronous completion request."""
    try:
        out = await router.acompletion(
            model="chutes/text",
            messages=[
                {"role": "system", "content": 'Return only {"ok":true} as JSON.'},
                {"role": "user", "content": "ping"},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            timeout=20,
        )
        c = out.choices[0].message.get("content")
        if not c:
            print("error: empty content")
            return 3
        print("ok", c if isinstance(c, str) else json.dumps(c))
        return 0
    except Exception as e:
        print(f"error: {e}")
        return 4
    finally:
        try:
            await router.aclose()
        except Exception:
            pass


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
