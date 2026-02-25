import pytest
from extractor.pipeline.steps.s04_section_builder import (
    _filter_toc_noise,
    _merge_short_sections,
    _is_partial_sentence,
    _section_content_length,
)


def test_filter_toc_noise():
    sections = [
        {"title": "Valid Section", "content": "This is normal content without dots."},
        {"title": "TOC Noise", "content": "Chapter 1 ........................ 5"},
        {"title": "Short Valid", "content": "This is short but has no dots."}
    ]
    # Convert to list of dicts for the function
    filtered = _filter_toc_noise(sections)
    assert len(filtered) == 2
    assert "TOC Noise" not in [s["title"] for s in filtered]

def test_merge_short_sections():
    sections = [
        {"title": "Section 1", "content": "This is a long-ish section content. " * 10, "pages": [1]},
        {"title": "Bullet 1", "content": "Short bullet point 1", "pages": [1]},
        {"title": "Bullet 2", "content": "Short bullet point 2", "pages": [2]},
        {"title": "Section 2", "content": "Another long section content. " * 10, "pages": [3]}
    ]
    merged = _merge_short_sections(sections)
    assert len(merged) == 2
    assert "Short bullet point 1" in merged[0]["content"]
    assert "Short bullet point 2" in merged[0]["content"]
    assert merged[0]["pages"] == [1, 2]

def test_is_partial_sentence_long_text():
    """Text > 120 chars should be flagged as partial sentence."""
    assert _is_partial_sentence("A" * 121) is True
    assert _is_partial_sentence("A" * 50) is False


def test_is_partial_sentence_lowercase_start():
    """Text starting with lowercase should be flagged."""
    assert _is_partial_sentence("and then the system shall") is True
    assert _is_partial_sentence("The system shall") is False


def test_is_partial_sentence_comma_ending():
    """Text ending with comma or semicolon should be flagged."""
    assert _is_partial_sentence("V&V Plan,") is True
    assert _is_partial_sentence("including sub-systems;") is True
    assert _is_partial_sentence("Complete Section.") is False


def test_is_partial_sentence_continuation_words():
    """Text starting with continuation words should be flagged."""
    for word in ["and ", "or ", "but ", "including ", "such as "]:
        assert _is_partial_sentence(word + "more text") is True, f"Failed for '{word}'"


def test_is_partial_sentence_internal_markers():
    """Text with internal markers like 'such as', 'e.g.' should be flagged."""
    assert _is_partial_sentence("Things such as widgets") is True
    assert _is_partial_sentence("For example, e.g. something") is True
    assert _is_partial_sentence("Normal Section Title") is False


def test_is_partial_sentence_empty():
    """Empty string should not be flagged."""
    assert _is_partial_sentence("") is False
    assert _is_partial_sentence("   ") is False


def test_section_content_length_from_content():
    """Content length from content field."""
    section = {"content": "Hello World"}
    assert _section_content_length(section) == 11


def test_section_content_length_from_blocks():
    """Content length from blocks when content is empty."""
    section = {
        "content": "",
        "blocks": [
            {"text": "Hello"},
            {"text": "World"},
        ],
    }
    assert _section_content_length(section) == 10


def test_section_content_length_empty():
    """Empty section returns 0."""
    assert _section_content_length({}) == 0
    assert _section_content_length({"content": "", "blocks": []}) == 0


def test_merge_preserves_numbered_sections():
    """Sections with numbered titles (e.g., 1.0, 2.1) should never be merged."""
    sections = [
        {"title": "Section 1", "content": "A" * 600, "pages": [1]},
        {"title": "1.1 Short Subsection", "content": "Brief.", "pages": [1]},
        {"title": "1.2 Another Short", "content": "Also brief.", "pages": [2]},
    ]
    merged = _merge_short_sections(sections)
    assert len(merged) == 3
    assert merged[1]["title"] == "1.1 Short Subsection"
    assert merged[2]["title"] == "1.2 Another Short"


def test_merge_uses_block_text_for_length():
    """Merge should consider block text when content is empty."""
    sections = [
        {
            "title": "Long Section",
            "content": "",
            "blocks": [{"text": "A" * 600}],
            "pages": [1],
        },
        {
            "title": "Short Following",
            "content": "",
            "blocks": [{"text": "Brief"}],
            "pages": [1],
        },
    ]
    merged = _merge_short_sections(sections)
    # Short section should merge into long section (prev_len >= 500 so it won't merge)
    # Actually: curr_len=5 < 150 but prev_len=600 >= 500, so NO merge
    assert len(merged) == 2


if __name__ == "__main__":
    test_filter_toc_noise()
    test_merge_short_sections()
    test_is_partial_sentence_long_text()
    test_is_partial_sentence_lowercase_start()
    test_is_partial_sentence_comma_ending()
    test_is_partial_sentence_continuation_words()
    test_is_partial_sentence_internal_markers()
    test_is_partial_sentence_empty()
    test_section_content_length_from_content()
    test_section_content_length_from_blocks()
    test_section_content_length_empty()
    test_merge_preserves_numbered_sections()
    test_merge_uses_block_text_for_length()
    print("S04 quality tests passed!")
