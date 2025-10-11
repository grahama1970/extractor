import pytest

from extractor.pipeline.utils.json_utils import parse_json_strict, STRICT_JSON_GUARD


def test_parse_json_strict_accepts_valid_object():
    payload = '{"a":1,"b":[2,3],"c":null}'
    parsed = parse_json_strict(payload)
    assert isinstance(parsed, dict)
    assert parsed["a"] == 1
    assert parsed["b"] == [2, 3]
    assert parsed["c"] is None


@pytest.mark.parametrize(
    "bad",
    [
        "```json\n{\n  \"x\": 1\n}\n```",  # fenced
        "Not JSON at all {x:1}",        # prose prefix
        "{\"val\": NaN}",            # forbidden constant
        "[1,2,3",                       # truncated
    ],
)
def test_parse_json_strict_rejects_non_strict(bad):
    with pytest.raises(ValueError):
        parse_json_strict(bad)


def test_strict_guard_text_present():
    # Quick smoke to ensure the guard stays definitive
    assert "No markdown" in STRICT_JSON_GUARD
    assert "No prose" in STRICT_JSON_GUARD or "no prose" in STRICT_JSON_GUARD
