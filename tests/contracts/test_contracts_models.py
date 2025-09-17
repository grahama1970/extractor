import os
import sys
import pytest

# Ensure 'src' is importable
sys.path.insert(0, os.path.abspath("src"))
from contracts import HeaderVerdict, ReflowedSection, SectionSummary


def test_header_verdict_strict_keys():
    ok = HeaderVerdict(
        doc_id="doc1",
        section_id="s1",
        verdict="accept",
        reasons=["clear numbering"],
        prompt_version="header@0.1.0",
        model_id="openai/gpt-4o-mini",
    )
    assert ok.verdict == "accept"

    # Extra key should be rejected
    with pytest.raises(Exception):
        HeaderVerdict(
            doc_id="doc1",
            section_id="s1",
            verdict="accept",
            reasons=[],
            prompt_version="v",
            model_id="m",
            extra_field=True,  # type: ignore[arg-type]
        )


def test_reflowed_section_requires_reflowed_json():
    rj = {"blocks": []}
    ok = ReflowedSection(
        doc_id="doc",
        section_id="sec",
        reflowed_json=rj,
        summary="short",
        prompt_version="reflow@0.1.0",
        model_id="gemini/gemini-2.5-flash",
    )
    assert ok.reflowed_json == rj

    # Missing required key
    with pytest.raises(Exception):
        ReflowedSection(
            doc_id="doc",
            section_id="sec",
            summary="short",
            prompt_version="reflow@0.1.0",
            model_id="gemini/gemini-2.5-flash",
        )  # type: ignore[call-arg]


def test_section_summary_strict():
    ok = SectionSummary(
        doc_id="doc",
        section_id="sec",
        summary_json={"bullets": ["a", "b"]},
        prompt_version="sum@0.1.0",
        model_id="openai/gpt-4o-mini",
    )
    assert ok.summary_json["bullets"] == ["a", "b"]

    with pytest.raises(Exception):
        SectionSummary(
            doc_id="doc",
            section_id="sec",
            summary_json={"bullets": ["a"]},
            prompt_version="sum@0.1.0",
            model_id="openai/gpt-4o-mini",
            extra=True,  # type: ignore[arg-type]
        )
