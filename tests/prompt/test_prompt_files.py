import pytest
from extractor.pipeline.utils.prompt_loader import load_prompt, PromptLoadError

PROMPT_NAMES = [
    "01_annotation_processor",
    "03_suspicious_headers",
    "07_reflow_section",
    "09_section_summarizer",
]


@pytest.mark.parametrize("name", PROMPT_NAMES)
def test_prompt_loads_and_has_required_fields(name):
    data = load_prompt(name)
    assert isinstance(data, dict)
    assert data.get("system") and data.get("user")
    assert isinstance(data["system"], str) and isinstance(data["user"], str)


def test_unknown_prompt_raises():
    with pytest.raises(PromptLoadError):
        load_prompt("does_not_exist_prompt")
