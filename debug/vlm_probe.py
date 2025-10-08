#!/usr/bin/env python3
"""
VLM Probe Script

Probes a set of OpenAI-compatible (Chutes) model identifiers and records
success / failure without hanging the pipeline. Intended for quick CI/
local validation of routing + credentials.

Usage:
  PYTHONPATH=./src python debug/vlm_probe.py --output scripts/artifacts/vlm_probe_report.json
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
import asyncio
from typing import List, Dict, Any

# Bridge CHUTES_* to OPENAI_* if unset
if (os.getenv("CHUTES_API_BASE") and os.getenv("CHUTES_API_KEY")):
    os.environ.setdefault("OPENAI_BASE_URL", os.getenv("CHUTES_API_BASE", "https://llm.chutes.ai/v1"))
    os.environ.setdefault("OPENAI_API_KEY", os.getenv("CHUTES_API_KEY"))

# Import after env bridging
try:
    from extractor.pipeline.utils.litellm_call import litellm_call
except Exception as e:
    print(f"Failed to import litellm_call: {e}", file=sys.stderr)
    sys.exit(2)


TARGET_MODELS = [
    "openai/chutesai/Mistral-Small-3.1-24B-Instruct-2503",
    "openai/deepseek-ai/DeepSeek-V3-0324",
    "openai/zai-org/GLM-4.5-Air",
    "openai/deepseek-ai/DeepSeek-R1",
]

PROMPT = 'Return only {"ok":true} as JSON.'

async def _probe_one(model: str, timeout: int) -> Dict[str, Any]:
    record: Dict[str, Any] = {"model": model, "ok": False}
    try:
        res = await litellm_call(
            [ {"model": model, "messages": [{"role":"user","content":[{"type":"text","text":PROMPT}]}], "timeout": timeout} ],
            wrap_json=True,
            concurrency=1,
            desc=f"probe:{model}",
            num_retries=0,
            request_timeout=timeout,
            export="results",
            show_progress=False,
        )
        r0 = res[0] if res else None
        content = (r0.content if r0 else "") or ""
        record["raw"] = content[:300]
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                record["ok"] = data.get("ok") is True or (
                    isinstance(data.get("content"), dict) and data["content"].get("ok") is True
                )
        except Exception:
            record["ok"] = False
        if r0 and r0.exception:
            record["error"] = type(r0.exception).__name__
    except Exception as e:
        record["error"] = f"{type(e).__name__}: {e}"
    return record


async def _run(models: List[str], timeout: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for m in models:
        out.append(await _probe_one(m, timeout))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", "-o", type=str, default="scripts/artifacts/vlm_probe_report.json")
    ap.add_argument("--timeout", type=int, default=25, help="Per-model timeout (seconds)")
    args = ap.parse_args()

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    results = asyncio.run(_run(TARGET_MODELS, args.timeout))
    summary = {
        "api_base": os.getenv("OPENAI_BASE_URL") or os.getenv("CHUTES_API_BASE"),
        "models_tested": len(results),
        "results": results,
        "all_ok": all(r.get("ok") for r in results),
    }
    Path(args.output).write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if not summary["all_ok"]:
        sys.exit(3)


if __name__ == "__main__":
    main()
