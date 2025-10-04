#!/usr/bin/env python3
"""Small Litellm smoke test against Chutes.ai (Qwen2.5-VL-32B-Instruct)."""

from __future__ import annotations

import json
import os
import sys

try:
    import litellm
except Exception as exc:  # pragma: no cover
    print(f"Litellm import failed: {exc}", file=sys.stderr)
    sys.exit(2)


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name) or default
    if value is None:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def main() -> int:
    model_alias = env("CHUTES_MODEL", "chutes/Qwen2.5-VL-32B-Instruct")
    api_key = env("CHUTES_API_KEY")
    api_base = env("CHUTES_API_BASE", "https://llm.chutes.ai/v1")
    provider = (os.getenv("CHUTES_PROVIDER") or "openai").strip() or "openai"
    actual_model = os.getenv("CHUTES_REMOTE_MODEL")
    if not actual_model:
        actual_model = model_alias.split("/", 1)[1] if "/" in model_alias else model_alias

    print(f"Using model alias={model_alias} actual_model={actual_model}")
    try:
        response = litellm.completion(
            model=actual_model,
            messages=[
                {"role": "system", "content": "You are a concise assistant."},
                {"role": "user", "content": "Return only the JSON {\"ok\": true, \"provider\": \"chutes\"}."},
            ],
            api_key=api_key,
            api_base=api_base,
            custom_llm_provider=provider,
            timeout=30,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        print(f"Chutes call error: {exc}", file=sys.stderr)
        return 3

    try:
        content = response["choices"][0]["message"]["content"]
    except Exception:
        content = str(response)

    print("Raw content:\n", content)
    try:
        data = json.loads(content)
        print("Parsed JSON:", data)
    except Exception as exc:
        print(f"NOTE: content was not strict JSON ({exc})", file=sys.stderr)
        return 4

    if data.get("ok") is True and data.get("provider") == "chutes":
        print("OK: Chutes Litellm call succeeded.")
        return 0

    print("Unexpected JSON payload", data, file=sys.stderr)
    return 5


if __name__ == "__main__":
    sys.exit(main())
