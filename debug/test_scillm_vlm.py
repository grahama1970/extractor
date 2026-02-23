#!/usr/bin/env python3
"""
Smoke: SciLLM/Router vision-capable sanity using your VLM alias.
Uses a text-only JSON prompt to verify routing/JSON handling.
"""
import os
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from extractor.pipeline.utils.litellm_call import list_models, completion_simple


def main() -> int:
    model = (
        os.getenv("LITELLM_VLM_MODEL")
        or os.getenv("LITELLM_MED_VLM_MODEL")
        or os.getenv("LITELLM_LARGE_VLLM_MODEL")
        or os.getenv("LITELLM_DEFAULT_MODEL")
        or "openai/gpt-4o-mini"
    )
    # Map Chutes → OpenAI-compatible env if present
    if os.getenv("CHUTES_API_KEY") and os.getenv("CHUTES_API_BASE"):
        os.environ.setdefault("OPENAI_API_KEY", os.environ["CHUTES_API_KEY"])  # key reuse
        os.environ.setdefault("OPENAI_API_BASE", os.environ["CHUTES_API_BASE"])  # base reuse

    # Prefer a VLM from catalog if available
    ids = list_models(ttl_sec=120)
    if ids:
        for cand in ids:
            if any(s in cand.lower() for s in ("vl", "vision", "gpt-4o", "qwen-vl", "kimi-vl")):
                model = cand
                break
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
