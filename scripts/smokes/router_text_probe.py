#!/usr/bin/env python3
"""
Router TEXT JSON-mode probe for Chutes via SciLLM (no wrappers).

Reads env:
  - CHUTES_API_BASE, CHUTES_API_KEY
  - CHUTES_TEXT_MODEL, CHUTES_TEXT_MODEL_ALT1, CHUTES_TEXT_MODEL_ALT2 (optional)
  - Writes artifacts under scripts/artifacts/.

Success prints the served model id and {"ok": true} JSON content.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

from litellm import Router  # SciLLM-compatible Router


def build_router() -> Router:
    base = os.environ["CHUTES_API_BASE"]
    key = os.environ["CHUTES_API_KEY"]
    m0 = os.environ.get("CHUTES_TEXT_MODEL", "").strip()
    m1 = os.environ.get("CHUTES_TEXT_MODEL_ALT1", "").strip()
    m2 = os.environ.get("CHUTES_TEXT_MODEL_ALT2", "").strip()

    if not m0:
        raise RuntimeError("CHUTES_TEXT_MODEL is not set")

    def entry(model: str, order: int) -> Dict[str, Any]:
        return {
            "model_name": "chutes/text",
            "litellm_params": {
                "custom_llm_provider": "openai_like",
                "model": model,
                "api_base": base,
                "api_key": key,
            },
            "order": order,
        }

    lst: List[Dict[str, Any]] = [entry(m0, 1)]
    if m1:
        lst.append(entry(m1, 2))
    if m2:
        lst.append(entry(m2, 3))
    return Router(model_list=lst)


def main() -> None:
    artifacts_dir = Path("scripts/artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    req_path = artifacts_dir / f"router_text_probe.request.{ts}.json"
    resp_path = artifacts_dir / f"router_text_probe.response.{ts}.json"
    meta_path = artifacts_dir / f"router_text_probe.meta.{ts}.json"

    messages = [
        {"role": "user", "content": "Return only {\"ok\": true} as JSON."}
    ]
    request_dump = {
        "model_group": "chutes/text",
        "messages": messages,
        "response_format": {"type": "json_object"},
    }
    req_path.write_text(json.dumps(request_dump, indent=2))

    router = build_router()
    out = router.completion(
        model="chutes/text",
        messages=messages,
        response_format={"type": "json_object"},
    )
    # Normalize content (string or dict) to dict
    content = out.choices[0].message.get("content")
    if isinstance(content, str):
        try:
            content_obj = json.loads(content)
        except json.JSONDecodeError:
            content_obj = {"raw": content}
    else:
        content_obj = content

    result = {
        "served_model": getattr(out, "model", None),
        "content": content_obj,
    }
    resp_path.write_text(json.dumps(result, indent=2))
    meta = {
        "ok": True,
        "served_model": result["served_model"],
        "artifacts": {
            "request": str(req_path),
            "response": str(resp_path),
        },
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"served_model= {result['served_model']}")
    print(json.dumps(result["content"]))


if __name__ == "__main__":
    main()

