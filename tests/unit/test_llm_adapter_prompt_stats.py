import os
import sys

# Ensure 'src' is importable when running tests directly
sys.path.insert(0, os.path.abspath("src"))

from llm_adapter.adapter import LLMAdapter


def test_prompt_stats_counts_plain_strings():
    """Verifies prompt stats count characters and messages from plain strings."""
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]

    stats = LLMAdapter._prompt_stats(messages)

    assert stats == {"prompt_chars": 10, "prompt_messages": 2}


def test_prompt_stats_skips_type_metadata():
    """Verify prompt stats calculation skips type metadata."""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "abc"},
                {"type": "text", "text": "def"},
            ],
        }
    ]

    stats = LLMAdapter._prompt_stats(messages)

    # Only count actual text payloads, not the 'type' field values
    assert stats == {"prompt_chars": 6, "prompt_messages": 1}


def test_prompt_stats_handles_nested_collections():
    """Test prompt stats processing of nested message collections."""
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "outer",
                    "metadata": {"note": "inner"},
                }
            ],
        },
        {"role": "assistant", "content": None},
    ]

    stats = LLMAdapter._prompt_stats(messages)

    # Should count both 'outer' and 'inner' strings, skip None entries
    assert stats == {"prompt_chars": len("outer") + len("inner"), "prompt_messages": 2}
