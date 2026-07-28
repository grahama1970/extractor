import importlib.util
import os
import sys

sys.path.insert(0, os.path.abspath("src"))


def _load_mod():
    """Load the s04_section_builder module from its file path."""
    spec = importlib.util.spec_from_file_location(
        "stage04", "src/extractor/pipeline/steps/s04_section_builder.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def test_build_sections_from_minimal_blocks():
    """Build sections from minimal block data for document processing."""
    mod = _load_mod()
    build = getattr(mod, "build_sections_from_blocks")
    # Minimal verified-like blocks: header + two text blocks
    blocks = [
        {"block_type": "SectionHeader", "text": "1. Intro", "page_idx": 0, "bbox": [0, 0, 100, 20]},
        {
            "block_type": "Text",
            "text": "This is the intro.",
            "page_idx": 0,
            "bbox": [0, 30, 200, 60],
        },
        {"block_type": "Text", "text": "More text.", "page_idx": 0, "bbox": [0, 65, 200, 90]},
    ]
    sections = build(blocks, fallback_heuristics=True)
    assert isinstance(sections, list)
    assert sections and sections[0].get("title")
    assert sections[0].get("level") == 1 or sections[0].get("level") is not None
    assert isinstance(sections[0].get("blocks", []), list)
