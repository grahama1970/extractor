"""
Test native XML extraction with security and modern standards
"""

import pytest
import tempfile
import time
from pathlib import Path
from datetime import datetime

from marker.core.providers.xml_native import NativeXMLProvider, LXML_AVAILABLE, DEFUSED_AVAILABLE
from marker.core.schema.unified_document import (
    UnifiedDocument, BlockType, SourceType, BaseBlock, TableBlock
)


class TestNativeXMLExtractor:
    """Test native XML extraction functionality"""
    
    def test_simple_xml(self):
        """Test extraction of simple XML document"""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <document>
            <title>Test Document</title>
            <author>Test Author</author>
            <created>2024-01-01T00:00:00</created>
            <content>
                <section>
                    <heading>Introduction</heading>
                    <paragraph>This is a test paragraph.</paragraph>
                </section>
                <section>
                    <heading>Conclusion</heading>
                    <paragraph>This concludes the test.</paragraph>
                </section>
            </content>
        </document>
        """
        
        with tempfile.NamedTemporaryFile(suffix='.xml', delete=False, mode='w') as f:
            f.write(xml_content)
            temp_path = Path(f.name)
        
        try:
            # Extract
            start_time = time.time()
            provider = NativeXMLProvider()
            extracted_doc = provider.extract_document(temp_path)
            duration = time.time() - start_time
            
            # Verify extraction
            assert extracted_doc.source_type == SourceType.XML
            assert extracted_doc.metadata.title == "Test Document"
            assert extracted_doc.metadata.author == "Test Author"
            
            # Check metadata
            assert extracted_doc.metadata.format_metadata['file_type'] == 'xml'
            assert extracted_doc.metadata.format_metadata['root_tag'] == 'document'
            
            # Check blocks
            assert len(extracted_doc.blocks) > 0
            
            # Check headings
            heading_blocks = [b for b in extracted_doc.blocks if b.type == BlockType.HEADING]
            assert len(heading_blocks) >= 2
            
            heading_texts = [b.content for b in heading_blocks]
            assert "Introduction" in heading_texts
            assert "Conclusion" in heading_texts
            
            # Check paragraphs
            para_blocks = [b for b in extracted_doc.blocks if b.type == BlockType.PARAGRAPH]
            assert len(para_blocks) >= 2
            
            # Duration check
            assert duration < 1.0
            
        finally:
            temp_path.unlink()
    
    def test_xml_with_namespaces(self):
        """Test extraction of XML with namespaces"""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <doc:document xmlns:doc="http://example.com/doc" xmlns:meta="http://example.com/meta">
            <meta:title>Namespaced Document</meta:title>
            <doc:content>
                <doc:paragraph>Content with namespaces.</doc:paragraph>
            </doc:content>
        </doc:document>
        """
        
        with tempfile.NamedTemporaryFile(suffix='.xml', delete=False, mode='w') as f:
            f.write(xml_content)
            temp_path = Path(f.name)
        
        try:
            provider = NativeXMLProvider(config={'preserve_namespaces': True})
            extracted_doc = provider.extract_document(temp_path)
            
            # Check namespaces preserved
            namespaces = extracted_doc.metadata.format_metadata.get('namespaces', {})
            assert len(namespaces) > 0
            
            # Check that namespace prefixes are preserved in metadata
            if LXML_AVAILABLE:
                assert 'doc' in namespaces or 'http://example.com/doc' in str(namespaces)
            
            # Check content extracted despite namespaces
            assert len(extracted_doc.blocks) > 0
            
            # Find the paragraph
            para_found = False
            for block in extracted_doc.blocks:
                if "Content with namespaces" in block.content:
                    para_found = True
                    break
            assert para_found
            
        finally:
            temp_path.unlink()
    
    def test_xml_table_detection(self):
        """Test automatic table detection in XML"""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <data>
            <records>
                <record>
                    <name>Item 1</name>
                    <value>100</value>
                    <status>Active</status>
                </record>
                <record>
                    <name>Item 2</name>
                    <value>200</value>
                    <status>Pending</status>
                </record>
                <record>
                    <name>Item 3</name>
                    <value>300</value>
                    <status>Complete</status>
                </record>
            </records>
        </data>
        """
        
        with tempfile.NamedTemporaryFile(suffix='.xml', delete=False, mode='w') as f:
            f.write(xml_content)
            temp_path = Path(f.name)
        
        try:
            provider = NativeXMLProvider()
            extracted_doc = provider.extract_document(temp_path)
            
            # Check for detected tables
            table_blocks = [b for b in extracted_doc.blocks if b.type == BlockType.TABLE]
            assert len(table_blocks) >= 1
            
            # Verify table structure
            table = table_blocks[0]
            assert table.rows == 4  # Header + 3 data rows
            assert table.cols == 3  # name, value, status
            
            # Check table content
            table_texts = [cell.content for cell in table.cells]
            assert "name" in table_texts  # Header
            assert "Item 1" in table_texts
            assert "200" in table_texts
            assert "Complete" in table_texts
            
        finally:
            temp_path.unlink()
    
    def test_xpath_queries(self):
        """Test XPath query extraction"""
        if not LXML_AVAILABLE:
            pytest.skip("lxml not available for XPath queries")
            
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <catalog>
            <book id="1">
                <title>Book One</title>
                <author>Author One</author>
                <price>29.99</price>
            </book>
            <book id="2">
                <title>Book Two</title>
                <author>Author Two</author>
                <price>39.99</price>
            </book>
        </catalog>
        """
        
        with tempfile.NamedTemporaryFile(suffix='.xml', delete=False, mode='w') as f:
            f.write(xml_content)
            temp_path = Path(f.name)
        
        try:
            # Configure XPath queries
            config = {
                'use_lxml': True,
                'xpath_queries': {
                    'book_titles': '//book/title/text()',
                    'expensive_books': '//book[price > 30]/title/text()'
                }
            }
            
            provider = NativeXMLProvider(config=config)
            extracted_doc = provider.extract_document(temp_path)
            
            # Check that XPath results are in blocks
            xpath_blocks = [b for b in extracted_doc.blocks 
                          if b.metadata.attributes.get('xpath_query') is not None]
            assert len(xpath_blocks) >= 3  # 2 book titles + 1 expensive book
            
            # Verify XPath results
            book_title_found = False
            expensive_found = False
            
            for block in xpath_blocks:
                if block.metadata.attributes['xpath_query'] == 'book_titles':
                    if "Book One" in block.content or "Book Two" in block.content:
                        book_title_found = True
                elif block.metadata.attributes['xpath_query'] == 'expensive_books':
                    if "Book Two" in block.content:
                        expensive_found = True
            
            assert book_title_found
            assert expensive_found
            
        finally:
            temp_path.unlink()
    
    def test_security_malicious_xml(self):
        """Test handling of potentially malicious XML"""
        # XML with entity expansion attack (billion laughs)
        malicious_xml = """<?xml version="1.0"?>
        <!DOCTYPE lolz [
          <!ENTITY lol "lol">
          <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
        ]>
        <lolz>&lol2;</lolz>
        """
        
        with tempfile.NamedTemporaryFile(suffix='.xml', delete=False, mode='w') as f:
            f.write(malicious_xml)
            temp_path = Path(f.name)
        
        try:
            # With secure parsing, this should either parse safely or raise an error
            provider = NativeXMLProvider(config={'secure_parsing': True})
            
            if DEFUSED_AVAILABLE:
                # defusedxml should handle this safely
                try:
                    extracted_doc = provider.extract_document(temp_path)
                    # If it parses, should have limited content
                    assert len(extracted_doc.blocks) < 100  # Not expanded
                except Exception as e:
                    # Or it might raise a safe parsing error
                    assert "entity" in str(e).lower() or "forbidden" in str(e).lower()
            else:
                # Without defusedxml, just ensure it doesn't crash
                extracted_doc = provider.extract_document(temp_path)
                assert extracted_doc is not None
                
        finally:
            temp_path.unlink()
    
    def test_attributes_extraction(self):
        """Test extraction of XML attributes"""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <document version="1.0" status="draft">
            <section id="intro" priority="high">
                <title>Introduction</title>
                <paragraph style="bold">Important text.</paragraph>
            </section>
        </document>
        """
        
        with tempfile.NamedTemporaryFile(suffix='.xml', delete=False, mode='w') as f:
            f.write(xml_content)
            temp_path = Path(f.name)
        
        try:
            provider = NativeXMLProvider(config={'extract_attributes': True})
            extracted_doc = provider.extract_document(temp_path)
            
            # Find blocks with attributes
            blocks_with_attrs = [b for b in extracted_doc.blocks 
                               if b.metadata.attributes.get('attributes')]
            assert len(blocks_with_attrs) > 0
            
            # Check that attributes were extracted
            # The paragraph should have the style attribute
            style_found = False
            for block in extracted_doc.blocks:
                attrs = block.metadata.attributes.get('attributes', {})
                if attrs.get('style') == 'bold':
                    style_found = True
                    assert "Important text" in block.content
                    break
            
            assert style_found, "Paragraph with style='bold' not found"
            
        finally:
            temp_path.unlink()
    
    def test_cdata_sections(self):
        """Test extraction of CDATA sections"""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <document>
            <code><![CDATA[
                function example() {
                    return "<test> & special chars";
                }
            ]]></code>
            <description>Normal text</description>
        </document>
        """
        
        with tempfile.NamedTemporaryFile(suffix='.xml', delete=False, mode='w') as f:
            f.write(xml_content)
            temp_path = Path(f.name)
        
        try:
            provider = NativeXMLProvider()
            extracted_doc = provider.extract_document(temp_path)
            
            # Check that CDATA content was extracted
            code_found = False
            for block in extracted_doc.blocks:
                if 'function example()' in block.content:
                    assert '<test> & special chars' in block.content
                    code_found = True
                    break
            
            assert code_found
            
        finally:
            temp_path.unlink()
    
    def test_performance_large_xml(self):
        """Test performance with larger XML file"""
        # Generate a larger XML file
        xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>\n<root>']
        
        for i in range(100):
            xml_parts.append(f"""
            <item id="{i}">
                <name>Item {i}</name>
                <description>Description for item {i}</description>
                <value>{i * 10}</value>
            </item>
            """)
        
        xml_parts.append('</root>')
        xml_content = ''.join(xml_parts)
        
        with tempfile.NamedTemporaryFile(suffix='.xml', delete=False, mode='w') as f:
            f.write(xml_content)
            temp_path = Path(f.name)
        
        try:
            provider = NativeXMLProvider()
            
            start_time = time.time()
            extracted_doc = provider.extract_document(temp_path)
            duration = time.time() - start_time
            
            # Should handle 100 items quickly
            assert duration < 2.0
            
            # Verify content extracted
            assert len(extracted_doc.blocks) >= 300  # At least 3 fields per item
            
            # Check some content
            content_found = False
            for block in extracted_doc.blocks:
                if "Item 50" in block.content:
                    content_found = True
                    break
            
            assert content_found
            
        finally:
            temp_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])