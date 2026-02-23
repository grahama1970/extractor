import os
import sys
import pytest

# Ensure 'src' is importable
sys.path.insert(0, os.path.abspath("src"))
from llm_adapter.adapter import LLMAdapter


RUN = os.getenv("RUN_S07_TEXT_SMOKE") == "1"


@pytest.mark.skipif(not RUN, reason="RUN_S07_TEXT_SMOKE not set")
@pytest.mark.asyncio
async def test_stage07_text_only_adapter_returns_json(tmp_path):
    # Choose provider based on available API keys
    model = None
    if os.getenv("GEMINI_API_KEY"):
        model = os.getenv("LITELLM_DEFAULT_MODEL", "gemini/gemini-2.5-flash")
    elif os.getenv("OPENAI_API_KEY"):
        model = os.getenv("LITELLM_DEFAULT_MODEL", "openai/gpt-4o-mini")
    else:
        pytest.skip("No provider API key found (GEMINI_API_KEY or OPENAI_API_KEY)")

    adapter = LLMAdapter(logs_root=tmp_path / "logs")

    guard = (
        "You are a strict JSON reflow engine. Return ONLY a JSON object with keys: "
        "reflowed_json, ocr_corrections, improvements_made, summary. No code fences. "
        "Requirements: reflowed_json.blocks must preserve reading order and include: "
        "(a) a single merged table block when tables are fragmented/continued. The table title MUST start with 'INFERRED:'; "
        "(b) a figure block with a non-empty title, short caption, and image_ref when applicable. "
        "Always provide ocr_corrections and improvements_made; include summary."
    )
    context = "Section: 4.1.5.4. BHT (Branch History Table) submodule. Includes a branch history table and explanatory text."

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"{guard}\n\n{context}"},
            ],
        }
    ]

    result = await adapter.reflow_section(
        model=model,
        messages=messages,
        prompt_version="reflow@0.1.0",
        doc_id="bht",
        section_id="s0",
        request_id="smoke07-text",
        timeout=30,
    )

    assert isinstance(result.reflowed_json, dict)
    assert "blocks" in result.reflowed_json
