"""Tests for XMLProvider."""

from pathlib import Path

import pytest

from extractor.core.providers.xml import XMLProvider
from extractor.core.schema.unified_document import SourceType


@pytest.fixture
def sample_xml(tmp_path: Path) -> Path:
    """Create a minimal XML file for testing."""
    xml_path = tmp_path / "test.xml"
    xml_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<document>
    <title>Test Document</title>
    <section id="s1">
        <heading>Section 1</heading>
        <paragraph>This is content.</paragraph>
    </section>
</document>"""
    )
    return xml_path


def test_xml_provider_basic_extraction(sample_xml: Path):
    """Test basic XML extraction returns expected structure."""
    provider = XMLProvider()
    doc = provider.extract_document(sample_xml)

    assert doc.source_type == SourceType.XML
    assert len(doc.blocks) >= 1
    # Should extract text content from elements
    all_content = " ".join(b.content for b in doc.blocks if isinstance(b.content, str))
    assert "Test Document" in all_content or "Section 1" in all_content


def test_xml_provider_nested_elements(tmp_path: Path):
    """Test XML provider handles nested elements."""
    xml_path = tmp_path / "nested.xml"
    xml_path.write_text(
        """<?xml version="1.0"?>
<root>
    <level1>
        <level2>
            <level3>Deep content</level3>
        </level2>
    </level1>
</root>"""
    )

    provider = XMLProvider()
    doc = provider.extract_document(xml_path)

    assert doc.source_type == SourceType.XML
    # Should extract nested content
    all_content = " ".join(b.content for b in doc.blocks if isinstance(b.content, str))
    assert "Deep content" in all_content


def test_xml_provider_with_attributes(tmp_path: Path):
    """Test XML provider handles elements with attributes."""
    xml_path = tmp_path / "attrs.xml"
    xml_path.write_text(
        """<?xml version="1.0"?>
<catalog>
    <item id="1" type="book">
        <name>Python Guide</name>
        <price currency="USD">29.99</price>
    </item>
</catalog>"""
    )

    provider = XMLProvider(config={"extract_attributes": True})
    doc = provider.extract_document(xml_path)

    assert doc.source_type == SourceType.XML
    assert len(doc.blocks) >= 1


def test_xml_provider_empty_document(tmp_path: Path):
    """Test XML provider handles minimal documents."""
    xml_path = tmp_path / "empty.xml"
    xml_path.write_text("""<?xml version="1.0"?><root></root>""")

    provider = XMLProvider()
    doc = provider.extract_document(xml_path)

    assert doc.source_type == SourceType.XML
    assert doc.blocks is not None
