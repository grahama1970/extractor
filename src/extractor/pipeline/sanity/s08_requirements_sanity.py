from __future__ import annotations

"""Stage 08 sanity: verify parallel_acompletions_iter + JSON contract."""

import asyncio
import json
import os
from typing import Any, Dict, List

from dotenv import find_dotenv, load_dotenv
from scillm.batch import parallel_acompletions_iter


def _env_or_fail(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise RuntimeError(f"{name} not configured")
    return value


async def _run() -> int:
    load_dotenv(find_dotenv(usecwd=True), override=False)
    api_key = _env_or_fail("CHUTES_API_KEY")
    model = os.getenv("CHUTES_TEXT_MODEL", "moonshotai/Kimi-K2-Instruct-0905")
    api_base = os.getenv("SCILLM_API_BASE", "https://llm.chutes.ai/v1")

    payloads: List[Dict[str, Any]] = [
        {
            "model": model,
            "metadata": {"stage": "s08_requirements"},
            "messages": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract ALL requirements from the provided specification text. "
                                "Return JSON only with shape: "
                                '{"requirements":[{"id":"REQ-1","text":"...",'
                                '"citation_snippet":"...","priority":"High"}]}'
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Excerpt: The CPU shall record the last eight branch outcomes and "
                                "must expose them via the debug CSR."
                            ),
                        }
                    ],
                },
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
            "id": "req-sanity",
        }
    ]

    results: List[Dict[str, Any]] = []
    async for result in parallel_acompletions_iter(
        payloads,
        api_base=api_base,
        api_key=api_key,
        custom_llm_provider="openai_like",  # Required per SCILLM_PAVED_PATH_CONTRACT
        concurrency=1,
        timeout=45,
        wall_time_s=120,
        tenacious=False,
    ):
        results.append(result)

    if not results:
        raise RuntimeError("parallel_acompletions_iter yielded no results")

    first = results[0]
    if first.get("ok") is False:
        raise RuntimeError(f"LLM error: {first.get('error')}")

    data: Dict[str, Any] = {}
    parsed = first.get("parsed")
    if isinstance(parsed, dict):
        data = parsed
    else:
        content = first.get("content")
        if isinstance(content, str):
            data = json.loads(content)

    reqs = data.get("requirements")
    if not isinstance(reqs, list) or not reqs:
        raise RuntimeError(f"Requirements list missing in payload: {data}")
    sample = reqs[0]
    if not isinstance(sample, dict) or not sample.get("text"):
        raise RuntimeError("Requirement entry missing text content")
    print("✅ Stage 08 requirements sanity succeeded.")
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
