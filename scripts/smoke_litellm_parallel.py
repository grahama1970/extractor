#!/usr/bin/env python3
"""
Smoke test for litellm parallel helper integration.

This avoids any real network calls by patching Router with a FakeRouter that
returns a canned OpenAI-style response. It exercises:
- helper path (vendored or upstream), when enabled
- legacy fallback path, when disabled via env flag

Usage:
  python scripts/smoke_litellm_parallel.py --mode helper
  python scripts/smoke_litellm_parallel.py --mode legacy
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
from typing import Any, Dict, List


class _Resp:
    def __init__(self) -> None:
        self.usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
        self._hidden_params = {"response_cost": 0.0, "cache_hit": False}
        self.choices = [type("_C", (), {"text": None, "message": type("_M", (), {"content": "ok"})()})()]


class FakeRouter:
    def __init__(self, *args, **kwargs) -> None:  # signature match
        pass

    async def acompletion(self, *, model: str, messages: List[Dict[str, Any]], **kwargs) -> Any:
        # Minimal async stub that returns a ModelResponse-like shape
        return _Resp()


def run(mode: str) -> Dict[str, Any]:
    # Configure path
    if mode == "helper":
        os.environ.pop("LITELLM_PARALLEL_DISABLE", None)
    elif mode == "legacy":
        os.environ["LITELLM_PARALLEL_DISABLE"] = "true"
    else:
        raise SystemExit("--mode must be one of: helper, legacy")

    # Fresh import of litellm_call to read env flags
    from extractor.pipeline.utils import litellm_call as lc  # initial import
    importlib.reload(lc)

    # Patch Router to avoid any network calls
    lc.Router = FakeRouter  # type: ignore

    # Single prompt smoke
    import asyncio

    out = asyncio.run(lc.litellm_call(["hello"], show_progress=False))
    return {
        "mode": mode,
        "have_helpers": bool(getattr(lc, "_HAVE_PARALLEL_HELPERS", False)),
        "helpers_disabled": bool(getattr(lc, "PARALLEL_HELPERS_DISABLED", False)),
        "ok": (out == ["ok"]),
        "answers": out,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["helper", "legacy"]) 
    args = ap.parse_args()
    print(json.dumps(run(args.mode), ensure_ascii=False))


if __name__ == "__main__":
    main()

