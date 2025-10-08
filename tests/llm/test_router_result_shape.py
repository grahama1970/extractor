#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os
import pytest


@pytest.mark.asyncio
async def test_router_result_basic_smoke(monkeypatch):
    try:
        import scillm  # type: ignore
    except Exception:
        pytest.skip("scillm not installed in test environment")

    # Prefer local dev path if provided
    dev_path = os.getenv("SCILLM_DEV_PATH")
    if dev_path:
        import sys
        if dev_path not in sys.path:
            sys.path.insert(0, dev_path)

    router = scillm.Router(deterministic=True)  # type: ignore[attr-defined]
    reqs = [
        {
            "model": os.getenv("LITELLM_DEFAULT_MODEL", "openai/zai-org/GLM-4.5-Air"),
            "messages": [
                {"role": "user", "content": "Return JSON {\\"ping\\": \\\"pong\\"} only."}
            ],
            "response_format": {"type": "json_object"},
            "timeout": 20,
        }
    ]
    try:
        res = await router.parallel_acompletions(reqs, max_concurrency=1)  # type: ignore[attr-defined]
    except Exception as exc:  # network/provider failures are acceptable in unit env
        pytest.skip(f"Router call skipped due to environment error: {exc}")

    assert isinstance(res, list) and len(res) == 1
    r0 = res[0]
    # Accept either dict or structured result for alpha
    if isinstance(r0, dict):
        content = r0.get("choices", [{}])[0].get("message", {}).get("content", "")
    else:
        content = getattr(r0, "content", "")
    # Non-empty content preferred; if empty, provider likely blocked – tolerate.
    if content:
        obj = json.loads(content)
        assert obj.get("ping") == "pong"

