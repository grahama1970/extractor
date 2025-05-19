"""
Tests for section breadcrumb functionality.
"""
import os
import uuid
import tempfile
import pytest
import json
import re

from marker.renderers.markdown import MarkdownRenderer
from marker.schema.blocks.sectionheader import SectionHeader
from marker.schema import BlockTypes
from marker.schema.polygon import PolygonBox
from marker.schema.document import Document
from marker.utils.markdown_extractor import extract_from_markdown, remove_breadcrumbs


@pytest.fixture
def mock_document_with_sections():
    """Create a mock document with several sections."""
    document = Document()
    
    # Create a page
    page = document.add_page(page_id=0, width=500, height=1000)
    
    # Create section headers with different levels
    h1 = SectionHeader(
        polygon=PolygonBox(bbox=[10, 10, 490, 30], polygon=[[10, 10], [490, 10], [490, 30], [10, 30]]),
        heading_level=1,
        page_id=0,
        block_id=1,
        block_description="Section header"
    )
    
    h2_1 = SectionHeader(
        polygon=PolygonBox(bbox=[10, 40, 490, 60], polygon=[[10, 40], [490, 40], [490, 60], [10, 60]]),
        heading_level=2,
        page_id=0,
        block_id=2,
        block_description="Subsection header"
    )
    
    h3 = SectionHeader(
        polygon=PolygonBox(bbox=[10, 70, 490, 90], polygon=[[10, 70], [490, 70], [490, 90], [10, 90]]),
        heading_level=3,
        page_id=0,
        block_id=3,
        block_description="Sub-subsection header"
    )
    
    h2_2 = SectionHeader(
        polygon=PolygonBox(bbox=[10, 100, 490, 120], polygon=[[10, 100], [490, 100], [490, 120], [10, 120]]),
        heading_level=2,
        page_id=0,
        block_id=4,
        block_description="Another subsection header"
    )
    
    # Add content to the headers
    h1.structure = []
    document.add_block(h1)
    page.add_structure(h1)
    
    h2_1.structure = []
    document.add_block(h2_1)
    page.add_structure(h2_1)
    
    h3.structure = []
    document.add_block(h3)
    page.add_structure(h3)
    
    h2_2.structure = []
    document.add_block(h2_2)
    page.add_structure(h2_2)
    
    return document


def test_section_header_uuid_generation():
    """Test that section headers generate UUIDs."""
    header1 = SectionHeader(
        polygon=PolygonBox(bbox=[10, 10, 490, 30], polygon=[[10, 10], [490, 10], [490, 30], [10, 30]]),
        heading_level=1
    )
    header2 = SectionHeader(
        polygon=PolygonBox(bbox=[10, 40, 490, 60], polygon=[[10, 40], [490, 40], [490, 60], [10, 60]]),
        heading_level=2
    )
    
    # Verify that UUIDs are generated
    assert header1.section_uuid != ""
    assert header2.section_uuid != ""
    assert header1.section_uuid != header2.section_uuid
    
    # Verify that a UUID is valid
    uuid_obj = uuid.UUID(header1.section_uuid)
    assert uuid_obj.version == 4


def test_render_with_breadcrumbs(mock_document_with_sections):
    """Test that rendering produces markdown with breadcrumbs."""
    renderer = MarkdownRenderer(include_breadcrumbs=True)
    result = renderer(mock_document_with_sections)
    
    # Check that the markdown contains breadcrumb comments
    assert "<!-- SECTION_BREADCRUMB:" in result.markdown
    
    # Count the breadcrumb comments - should be one per heading
    breadcrumb_matches = re.findall(r'<!-- SECTION_BREADCRUMB: (.+?) -->', result.markdown)
    assert len(breadcrumb_matches) == 4
    
    # Parse the first breadcrumb to verify format
    first_breadcrumb = json.loads(breadcrumb_matches[0])
    assert isinstance(first_breadcrumb, list)
    assert len(first_breadcrumb) == 1  # First heading only has itself in breadcrumb
    assert "level" in first_breadcrumb[0]
    assert "title" in first_breadcrumb[0]
    assert "uuid" in first_breadcrumb[0]
    
    # Parse the third breadcrumb to verify hierarchy
    third_breadcrumb = json.loads(breadcrumb_matches[2])
    assert len(third_breadcrumb) == 3  # h3 should have h1, h2, and itself in breadcrumb
    assert third_breadcrumb[0]["level"] == 1
    assert third_breadcrumb[1]["level"] == 2
    assert third_breadcrumb[2]["level"] == 3


def test_extract_from_markdown(mock_document_with_sections):
    """Test extracting sections from markdown."""
    renderer = MarkdownRenderer(include_breadcrumbs=True)
    result = renderer(mock_document_with_sections)
    
    # Extract sections from markdown
    extracted = extract_from_markdown(result.markdown)
    
    # Verify structure of extracted data
    assert "sections" in extracted
    assert "section_hierarchy" in extracted
    assert len(extracted["sections"]) == 4
    
    # Verify content of first section
    assert "title" in extracted["sections"][0]
    assert "level" in extracted["sections"][0]
    assert "uuid" in extracted["sections"][0]
    assert "breadcrumb" in extracted["sections"][0]
    assert "content" in extracted["sections"][0]
    
    # Verify breadcrumb hierarchy
    first_uuid = extracted["sections"][0]["uuid"]
    assert first_uuid in extracted["section_hierarchy"]
    assert len(extracted["section_hierarchy"][first_uuid]) == 1  # Only itself
    
    # Verify hierarchy for h3
    h3_section = next((s for s in extracted["sections"] if s["level"] == 3), None)
    assert h3_section is not None
    assert len(h3_section["breadcrumb"]) == 3  # h1, h2, h3


def test_remove_breadcrumbs(mock_document_with_sections):
    """Test removing breadcrumbs from markdown."""
    renderer = MarkdownRenderer(include_breadcrumbs=True)
    result = renderer(mock_document_with_sections)
    
    # Remove breadcrumbs
    cleaned = remove_breadcrumbs(result.markdown)
    
    # Verify breadcrumbs are removed
    assert "<!-- SECTION_BREADCRUMB:" not in cleaned
    
    # Verify headings are preserved
    assert "# " in cleaned  # h1
    assert "## " in cleaned  # h2
    assert "### " in cleaned  # h3


def test_disable_breadcrumbs(mock_document_with_sections):
    """Test disabling breadcrumbs in the renderer."""
    renderer = MarkdownRenderer(include_breadcrumbs=False)
    result = renderer(mock_document_with_sections)
    
    # Verify no breadcrumbs in output
    assert "<!-- SECTION_BREADCRUMB:" not in result.markdown
    
    # Verify headings are present
    assert "# " in result.markdown
    assert "## " in result.markdown
    assert "### " in result.markdown