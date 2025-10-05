import json
import types
import asyncio
from pathlib import Path

import extractor.pipeline.steps._07_reflow_section as stage07  # path alias if needed


class DummyResult:
    def __init__(self, content: str):
        self.content = content
        self.request = types.SimpleNamespace(model="mock/deepseek")
        self.exception = None


async def _mock_litellm_call(prompts, **kwargs):
    payload = (
        "Here is your result:\n\n"
        "```json\n"
        "{\n"
        "  \"reflowed_json\": {\n"
        "    \"title\": \"Demo\",\n"
        "    \"blocks\": [\n"
        "      {\"type\":\"heading\",\"text\":\"Demo\",\"source\":{\"pages\":[],\"block_ids\":[]}},\n"
        "      {\"type\":\"paragraph\",\"text\":\"Hello World paragraph.\",\"source\":{\"pages\":[],\"block_ids\":[]}}\n"
        "    ]\n"
        "  },\n"
        "  \"ocr_corrections\": {},\n"
        "  \"improvements_made\": \"minor cleanup\",\n"
        "  \"summary\": \"Short summary.\"\n"
        "}\n"
        "```\n\nThanks!"
    )
    return [DummyResult(payload)]


def test_reflow_parses_fenced_payload(monkeypatch, tmp_path):
    monkeypatch.setenv("STAGE07_CONTEXT_TRIM_CHARS", "1000")
    monkeypatch.setenv("STAGE07_RETRY_TRIM_CHARS", "500")
    monkeypatch.setenv("STAGE07_FIRST_TOKEN_FRACTION", "0.7")
    monkeypatch.setattr(stage07, "litellm_call", _mock_litellm_call)

    section = {
        "id": "s1",
        "title": "Demo",
        "page_start": 1,
        "page_end": 1,
        "raw_text": "Hello World paragraph.",
        "tables": [],
        "figures": [],
        "blocks": [{"type": "Text", "text": "Hello World paragraph.", "page": 1}],
    }

    async def run():
        return await stage07.reflow_section_with_llm(
            section, tmp_path, include_images=False, allow_fallback=False, llm_timeout=30
        )

    result = asyncio.run(run())
    assert "reflowed_json" in result
    assert result["reflowed_json"]["title"] == "Demo"
    md = result.get("metadata", {})
    assert md.get("parse_strategy") is not None
