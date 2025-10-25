#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12.3",
#   "scillm>=0.1.0",
# ]
# ///

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

import typer
from scillm import Router


app = typer.Typer(add_completion=False)


def _env(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


def _model_id() -> str:
    # Prefer explicit CHUTES_TEXT_MODEL; otherwise a common text model name
    return _env("CHUTES_TEXT_MODEL", _env("LITELLM_MODEL", "deepseek-ai/DeepSeek-R1"))


def _router(model_id: str) -> Router:
    base = _env("CHUTES_API_BASE")
    key = _env("CHUTES_API_KEY")
    # OpenAI-like path with x-api-key header; SciLLM handles pacing/backoff
    return Router(
        model_list=[
            {
                "model_name": "chutes",
                "litellm_params": {
                    "model": model_id,
                    "custom_llm_provider": "openai_like",
                    "api_base": base,
                    "api_key": None,
                    "extra_headers": {"x-api-key": key},
                    "response_format": {"type": "json_object"},
                    "max_tokens": 128,
                    "temperature": 0,
                },
            }
        ],
        num_retries=1,
        default_max_parallel_requests=8,
    )


def _prompts(n: int) -> List[str]:
    base = 'Respond ONLY with a compact JSON object: {"ok": boolean, "n": number}.'
    return [base for _ in range(max(1, n))]


def _reqs(prompts: List[str], model_id: str) -> List[Dict[str, Any]]:
    return [
        {"model": model_id, "messages": [{"role": "user", "content": p}]}
        for p in prompts
    ]


def _content_json(resp: Dict[str, Any]) -> Dict[str, Any]:
    content = resp.get("choices", [{}])[0].get("message", {}).get("content")
    if isinstance(content, str):
        try:
            return json.loads(content)
        except Exception:
            return {"raw": content}
    return content or {}


@app.command()
def main(
    n: int = typer.Option(10, "--n", help="Number of prompts to run"),
    concurrency: int = typer.Option(8, "--concurrency", "-c", help="Parallel concurrency"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model id to use"),
    raw: bool = typer.Option(False, "--raw", help="Print raw responses"),
):
    model_id = model or _model_id()
    r = _router(model_id)
    reqs = _reqs(_prompts(n), model_id)

    async def _run():
        # Prefer built-in helper if available; otherwise run a bounded gather
        if hasattr(r, "parallel_acompletions"):
            outs = await r.parallel_acompletions(  # type: ignore[attr-defined]
                requests=reqs,
                concurrency=max(1, concurrency),
                return_exceptions=True,
            )
        else:
            sem = asyncio.Semaphore(max(1, concurrency))

            async def _one(req: Dict[str, Any]):
                async with sem:
                    try:
                        return await r.acompletion(**req)
                    except Exception as e:  # return exceptions to keep order
                        return e

            outs = await asyncio.gather(*[_one(req) for req in reqs], return_exceptions=False)
        for i, o in enumerate(outs):
            if isinstance(o, Exception):
                print(json.dumps({"i": i, "error": str(o)}))
                continue
            print(json.dumps({"i": i, "data": (o if raw else _content_json(o))}))

    asyncio.run(_run())


if __name__ == "__main__":  # pragma: no cover
    app()
