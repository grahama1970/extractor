#!/usr/bin/env python3
"""
Router Retry-After Floor Probe
------------------------------
Runs a single litellm_call with the model from env and prints a minimal
JSON result. Intended to verify that our Retry-After floor prevents
TypeError paths when providers return missing/None retry-after values.

Usage (venv + .env loaded):
  python debug/chutes/router_retry_floor_probe.py --model "$LITELLM_VLM_MODEL" --timeout 45

Exits 0 on success (even if the provider rate-limits), printing a JSON
record with {"ok": bool, "exception": str|None}.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

# Allow running outside package root (venv session)
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from extractor.pipeline.utils.litellm_call import litellm_call  # type: ignore


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.getenv("LITELLM_VLM_MODEL") or os.getenv("LITELLM_MED_VLM_MODEL") or "openai/Qwen/Qwen2.5-VL-32B-Instruct")
    ap.add_argument("--timeout", type=int, default=int(os.getenv("STAGE06_TIMEOUT", "60")))
    args = ap.parse_args()

    # A tiny image+text payload; router will attach provider automatically
    msgs = [
        {"role": "system", "content": "Return ONLY {\"ok\":true} as JSON."},
        {"role": "user", "content": [
            {"type": "text", "text": "vision retry-after floor probe"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB"}}
        ]},
    ]

    try:
        res = await litellm_call([
            {"model": args.model, "messages": msgs, "kwargs": {"timeout": args.timeout, "temperature": 0, "top_p": 1}}
        ], wrap_json=True, concurrency=1, desc="router_retry_floor_probe", export="results")
        ok = bool(res and res[0] and res[0].exception is None)
        out = {
            "model": args.model,
            "timeout": args.timeout,
            "ok": ok,
            "exception": None if ok else (str(res[0].exception) if res and res[0] else "unknown"),
        }
        print(json.dumps(out, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"model": args.model, "timeout": args.timeout, "ok": False, "exception": str(e)}))
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

