import json
from pathlib import Path

from extractor.pipeline.steps import s04_section_builder as stage04


def test_section_builder_minimal_numbered(tmp_path: Path):
    # Two numbered headers: 1. A, 1.1 B
    blocks = [
        {
            "block_type": "SectionHeader",
            "text": "1. Top Section",
            "bbox": [0, 0, 10, 10],
            "page_idx": 0,
            "suspicious_header": False,
        },
        {
            "block_type": "Text",
            "text": "Body under top section.",
            "bbox": [0, 0, 10, 10],
            "page_idx": 0,
        },
        {
            "block_type": "SectionHeader",
            "text": "1.1 Sub Section",
            "bbox": [0, 0, 10, 10],
            "page_idx": 0,
            "suspicious_header": False,
        },
        {
            "block_type": "Text",
            "text": "Child body.",
            "bbox": [0, 0, 10, 10],
            "page_idx": 0,
        },
    ]
    out = stage04.build_sections_from_blocks(blocks, fallback_heuristics=True)
    assert len(out) == 2
    top, child = out[0], out[1]
    assert top["section_number"].startswith("1")
    assert child["section_number"].startswith("1.1")
    assert child.get("parent_id") == top.get("id")
    # breadcrumb propagation
    assert "breadcrumb_titles" in child["metadata"]
    assert child["metadata"]["breadcrumb_titles"][0].startswith("1 ")


def test_section_builder_numeric_then_plain_title(tmp_path: Path):
    # Numeric header followed by plain uppercase title recognized by heuristic
    blocks = [
        {
            "block_type": "SectionHeader",
            "text": "2. Hardware Overview",
            "bbox": [0, 0, 10, 10],
            "page_idx": 0,
            "suspicious_header": False,
        },
        {
            "block_type": "SectionHeader",
            "text": "ACRONYMS AND DEFINITIONS",
            "bbox": [0, 0, 10, 10],
            "page_idx": 0,
            "suspicious_header": False,
        },
    ]
    out = stage04.build_sections_from_blocks(blocks, fallback_heuristics=True)
    assert len(out) == 2
    assert out[0]["section_number"].startswith("2")
    # Plain title should still become a section (heuristic)
    assert out[1]["title"].lower().startswith("acronyms")
