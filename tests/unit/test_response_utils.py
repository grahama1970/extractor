import json

import pytest

from extractor.pipeline.utils.litellm_response_utils import (
    extract_content,
    augment_json_with_cost,
    classify_error,
    format_error,
)


def test_extract_content_from_openai_like_dict_text_and_list_parts():
    """Extract text content from a structured OpenAI-like response."""
    resp = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "text", "text": "line1"},
                        {"type": "text", "text": "line2"},
                    ]
                }
            }
        ]
    }
    out = extract_content(resp)
    assert out == "line1\nline2"


class DummyResp:
    """Initialize a dummy response object with usage metrics."""
    def __init__(self):
        """Initialize usage statistics and hidden parameters."""
        self.usage = type(
            "U", (), {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}
        )()
        self._hidden_params = {"response_cost": 0.000001, "cache_hit": False}


def test_augment_json_with_cost_wraps_non_json_and_injects_metadata():
    """Augment JSON with cost metadata, wrapping non-JSON inputs."""
    text = "not json"
    out = augment_json_with_cost(text, DummyResp(), wrap_non_json=True)
    data = json.loads(out)
    assert data["content"] == text
    md = data["metadata"]
    assert md["token_usage"]["total_tokens"] == 5
    assert md["response_cost"] == 0.000001


def test_augment_json_with_cost_non_dict_metadata_goes_to_underscore():
    """Verifies non-dict metadata moves to underscore key when augmenting JSON."""
    class DummyResp2:
        """Represent a dummy API response with usage and cost data."""
        usage = {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}
        _hidden_params = {"response_cost": 0.1}

    text = json.dumps({"metadata": "string_instead_of_dict", "value": 1})
    out = augment_json_with_cost(text, DummyResp2(), wrap_non_json=False)
    data = json.loads(out)
    # Original non-dict metadata preserved; provider metadata stored under _metadata
    assert data["metadata"] == "string_instead_of_dict"
    assert data["_metadata"]["response_cost"] == 0.1


@pytest.mark.parametrize(
    "msg,category",
    [
        ("max_tokens too low", "token_limit"),
        ("does not support image input", "vision_unsupported"),
        ("Rate limit exceeded", "rate_limit"),
        ("Deadline exceeded timeout", "timeout"),
        ("invalid api key", "auth_error"),
        ("Service unavailable 503", "server_error"),
        ("connection reset by peer", "network_error"),
        ("insufficient_quota", "quota"),
        ("model not found", "model_not_found"),
        ("bad request", "bad_request"),
        ("content policy violation", "safety_block"),
        ("tool calls are not supported", "tools_unsupported"),
    ],
)
def test_classify_error_categories(msg, category):
    """Map error message to a predefined category."""
    err = classify_error(Exception(msg))
    assert err["category"] == category


def test_format_error_wrap_json_true():
    """Return formatted error message as JSON when wrap_json is True."""
    s = format_error(Exception("oops"), wrap_json=True)
    data = json.loads(s)
    assert "error" in data and data["error"]["message"]
