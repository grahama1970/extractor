#!/usr/bin/env python3
"""
Smoke: SciLLM/Router text sanity using your .env model aliases.
Prints a one-line JSON: {"ok": true} on success.
"""
import os
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from extractor.pipeline.utils.litellm_call import completion_simple


def main() -> int:
    model = (
        os.getenv("LITELLM_DEFAULT_MODEL")
        or os.getenv("LITELLM_MED_TEXT_MODEL")
        or os.getenv("LITELLM_SMALL_TEXT_MODEL")
        or "openai/gpt-4o-mini"
    )
    # Map Chutes → OpenAI-compatible env if present
    if os.getenv("CHUTES_API_KEY") and os.getenv("CHUTES_API_BASE"):
        os.environ.setdefault("OPENAI_API_KEY", os.environ["CHUTES_API_KEY"])  # key reuse
        os.environ.setdefault("OPENAI_API_BASE", os.environ["CHUTES_API_BASE"])  # base reuse

    # Prefer direct completion to avoid Router deployment health for sanity
    out = completion_simple(
        model=model,
        messages=[{"role": "user", "content": 'Return only {"ok":true} as JSON.'}],
    )
    content = (
        out.choices[0].message.get("content")
        if hasattr(out, "choices")
        else out.get("choices", [{}])[0].get("message", {}).get("content", "")
    )
    try:
        data = json.loads(content)
    except Exception:
        print(content)
        return 2
    print(json.dumps(data, ensure_ascii=False))
    return 0 if isinstance(data, dict) and data.get("ok") is True else 3


if __name__ == "__main__":
    raise SystemExit(main())
