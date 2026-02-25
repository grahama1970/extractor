import pytest
from pathlib import Path
from extractor.pipeline.steps.s04_section_builder import (
    _is_toc_or_page_header_footer,
    build_sections_from_blocks
)

def test_toc_filtering():
    # Test new V3 patterns
    assert _is_toc_or_page_header_footer("Introduction . . . . . . 1")
    assert _is_toc_or_page_header_footer("Chapter 1\t\t\t\t5")
    assert _is_toc_or_page_header_footer("Detailed Analysis\t.\t.\t.\t10")
    assert _is_toc_or_page_header_footer("Jkt 067464 PO 00000 Frm 00010")
    assert _is_toc_or_page_header_footer("PO 12345 Frm 67890")
    
    # Negative tests
    assert not _is_toc_or_page_header_footer("This is a normal sentence.")
    assert not _is_toc_or_page_header_footer("1. Introduction")

def test_mid_sentence_merging():
    blocks = [
        {
            "block_type": "SectionHeader",
            "text": "This header ends without punctuation",
            "page": 0,
            "bbox": [0, 0, 100, 20]
        },
        {
            "block_type": "SectionHeader",
            "text": "and continues here with lowercase",
            "page": 0,
            "bbox": [0, 25, 100, 45]
        },
        {
            "block_type": "Text",
            "text": "Normal body text.",
            "page": 0,
            "bbox": [0, 50, 100, 70]
        }
    ]
    
    sections = build_sections_from_blocks(blocks)
    # Should be merged into one section (excluding the final "Post-processing merges" which happens in build_sections_from_blocks)
    # Actually build_sections_from_blocks handles the merging in the post-processing loop.
    assert len(sections) == 1
    assert "continues here" in sections[0]["blocks"][1]["text"]

def test_slide_merging_sparse():
    # Create a sparse slide deck (very few words per page)
    blocks = []
    for i in range(10):
        # Header block
        blocks.append({
            "block_type": "SectionHeader",
            "text": f"Slide {i+1}",
            "page": i,
            "bbox": [0, 0, 100, 20]
        })
        # Sparse content
        blocks.append({
            "block_type": "Text",
            "text": "Point A",
            "page": i,
            "bbox": [0, 30, 100, 50]
        })
    
    # avg_words will be ~2 words per page (Slide N + Point A)
    # 50 words/page threshold. Sparse merging should trigger.
    sections = build_sections_from_blocks(blocks, is_slide_deck=True)
    
    # 10 pages, merge_size=5 (since avg < 15), should result in 2 sections
    assert len(sections) == 2
    assert sections[0]["metadata"]["is_merged_slides"] is True

if __name__ == "__main__":
    pytest.main([__file__])
