"""Tests for ImageProvider with VLM and OCR fallback."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from extractor.core.providers.image import ImageProvider, _parse_vlm_content_to_blocks
from extractor.core.schema.unified_document import BlockType, SourceType


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    """Create a minimal valid PNG file for testing."""
    from PIL import Image

    img_path = tmp_path / "test.png"
    img = Image.new("RGB", (100, 100), color="white")
    img.save(img_path)
    return img_path


def test_image_provider_basic_extraction(sample_image: Path):
    """Test basic extraction without VLM or OCR (no API key)."""
    with patch.dict(os.environ, {"CHUTES_API_KEY": ""}, clear=False):
        provider = ImageProvider(config={"use_vlm": False, "use_ocr": False})
        doc = provider.extract_document(sample_image)

    assert doc.source_type == SourceType.IMAGE
    assert len(doc.blocks) >= 1
    assert doc.blocks[0].type == BlockType.IMAGE


def test_image_provider_legacy_pattern(sample_image: Path):
    """Test legacy initialization pattern: ImageProvider(filepath)."""
    with patch.dict(os.environ, {"CHUTES_API_KEY": ""}, clear=False):
        provider = ImageProvider(str(sample_image), config={"use_vlm": False, "use_ocr": False})
        doc = provider.extract_document()

    assert doc.source_type == SourceType.IMAGE
    assert len(doc.blocks) >= 1


def test_parse_vlm_content_to_blocks_headings():
    """Test VLM content parsing extracts markdown headings."""
    content = """# Main Title
Some paragraph text.

## Section 1
More content here.

### Subsection 1.1
Details."""

    blocks = _parse_vlm_content_to_blocks(content, "test.png")

    headings = [b for b in blocks if b.type == BlockType.HEADING]
    paragraphs = [b for b in blocks if b.type == BlockType.PARAGRAPH]

    assert len(headings) == 3
    assert headings[0].content == "Main Title"
    assert headings[0].metadata.attributes["level"] == 1
    assert headings[1].metadata.attributes["level"] == 2
    assert headings[2].metadata.attributes["level"] == 3
    assert len(paragraphs) >= 2


def test_parse_vlm_content_to_blocks_numbered_headings():
    """Test VLM content parsing extracts numbered headings."""
    content = """1. Overview
Introduction text.

1.1 Scope
Scope details.

1.1.1 Subsection
More details."""

    blocks = _parse_vlm_content_to_blocks(content, "test.png")

    headings = [b for b in blocks if b.type == BlockType.HEADING]
    assert len(headings) == 3
    assert "1. Overview" in headings[0].content
    assert "1.1 Scope" in headings[1].content


def test_image_provider_multiframe_tiff(tmp_path: Path):
    """Test extraction from multi-frame image (TIFF)."""
    from PIL import Image

    tiff_path = tmp_path / "multi.tiff"
    frames = [Image.new("RGB", (50, 50), color=c) for c in ["red", "green", "blue"]]
    frames[0].save(tiff_path, save_all=True, append_images=frames[1:])

    with patch.dict(os.environ, {"CHUTES_API_KEY": ""}, clear=False):
        provider = ImageProvider(config={"use_vlm": False, "use_ocr": False})
        doc = provider.extract_document(tiff_path)

    # Should have one block per frame
    assert len(doc.blocks) == 3
    assert all(b.type == BlockType.IMAGE for b in doc.blocks)


def test_image_provider_context_manager(sample_image: Path):
    """Test ImageProvider works as context manager."""
    with patch.dict(os.environ, {"CHUTES_API_KEY": ""}, clear=False):
        with ImageProvider(
            str(sample_image), config={"use_vlm": False, "use_ocr": False}
        ) as provider:
            assert provider.image is not None
            assert provider.image_count == 1
