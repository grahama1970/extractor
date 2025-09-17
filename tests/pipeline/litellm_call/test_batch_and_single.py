import json
from typing import Any, Dict, List

import pytest

import extractor.pipeline.utils.litellm_call as lc


class FakeRouter:
    """Minimal fake of LiteLLM Router capturing acompletion calls.

    We force the legacy fallback path by setting lc._HAVE_PARALLEL_HELPERS = False
    in tests to avoid depending on optional parallel helpers.
    """

    last: "FakeRouter | None" = None

    def __init__(self, model_list: List[Dict[str, Any]], num_retries: int, default_max_parallel_requests: int | None):  # noqa: D401,E501
        self.model_list = model_list
        self.num_retries = num_retries
        self.default_max_parallel_requests = default_max_parallel_requests
        self.calls: List[Dict[str, Any]] = []
        FakeRouter.last = self

    async def acompletion(self, *, model: str, messages: List[Dict[str, Any]], **kwargs):
        self.calls.append({"model": model, "messages": messages, "kwargs": kwargs})
        # Return an OpenAI-like dict shape so extract_content() returns the content string
        return {
            "choices": [{"message": {"content": f"ok::{model}::{len(messages)}"}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }


@pytest.mark.asyncio
async def test_single_prompt_string_calls_router_once(monkeypatch):
    monkeypatch.setattr(lc, "Router", FakeRouter)
    monkeypatch.setattr(lc, "_HAVE_PARALLEL_HELPERS", False)

    out = await lc.litellm_call("Hello world")  # not a list
    assert isinstance(out, list) and len(out) == 1
    assert out[0].startswith("ok::")

    r = FakeRouter.last
    assert r is not None
    assert len(r.calls) == 1
    # Ensure messages were built (single user message)
    assert isinstance(r.calls[0]["messages"], list) and r.calls[0]["messages"]


@pytest.mark.asyncio
async def test_models_fanout_duplicates_prompts_per_model(monkeypatch):
    monkeypatch.setattr(lc, "Router", FakeRouter)
    monkeypatch.setattr(lc, "_HAVE_PARALLEL_HELPERS", False)

    models = ["openai/gpt-4o-mini", "anthropic/claude-3-5-haiku"]
    out = await lc.litellm_call("Hello", models=models)

    assert len(out) == 2
    r = FakeRouter.last
    assert r is not None
    assert {c["model"] for c in r.calls} == set(models)


@pytest.mark.asyncio
async def test_individual_params_preserved_in_kwargs(monkeypatch):
    monkeypatch.setattr(lc, "Router", FakeRouter)
    monkeypatch.setattr(lc, "_HAVE_PARALLEL_HELPERS", False)

    # Two prompts for the same model: one batchable (no extras), one with temperature (individual)
    prompts: List[Any] = [
        {  # batchable
            "model": lc.MODEL,
            "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        },
        {
            "model": lc.MODEL,
            "messages": [{"role": "user", "content": [{"type": "text", "text": "yo"}]}],
            "temperature": 0.7,
        },
    ]

    out = await lc.litellm_call(prompts)
    assert len(out) == 2

    r = FakeRouter.last
    assert r is not None
    assert len(r.calls) == 2
    # Identify the call that preserved per-request kwargs
    temps = [call for call in r.calls if call["kwargs"].get("temperature") == 0.7]
    assert len(temps) == 1
    # The batchable one should not carry temperature in kwargs
    noextras = [call for call in r.calls if not call["kwargs"].get("temperature")]
    assert len(noextras) == 1

