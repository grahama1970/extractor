#!/usr/bin/env python3
"""
Comprehensive test for the unified section summarizer
"""
import pytest
from unittest.mock import patch, MagicMock
from marker.processors.enhanced.summarizer import SectionSummarizer
from marker.schema.document import Document
from marker.schema.blocks.sectionheader import SectionHeader
from marker.schema.groups.page import PageGroup
from marker.schema.blocks.text import Text
from marker.schema import BlockTypes
from marker.schema.polygon import PolygonBox


def create_test_document():
    """Create a test document with sections and content"""
    doc = Document(
        filepath="test.pdf",
        pages=[],
        metadata={}
    )
    
    # Create page
    page = PageGroup(
        block_type=BlockTypes.PageGroup,
        block_id=0,
        page_id=0,
        polygon=PolygonBox(polygon=[[0, 0], [612, 0], [612, 792], [0, 792]], bbox=[0, 0, 612, 792]),
        children=[]
    )
    
    # Create main section
    section1 = SectionHeader(
        block_type=BlockTypes.SectionHeader,
        block_id=1,
        page_id=0,
        heading_level=1,
        text_extraction_method="pdftext",
        polygon=PolygonBox(polygon=[[0, 0], [100, 0], [100, 20], [0, 20]], bbox=[0, 0, 100, 20]),
        html="Introduction"
    )
    
    # Create subsection
    section2 = SectionHeader(
        block_type=BlockTypes.SectionHeader,
        block_id=2,
        page_id=0,
        heading_level=2,
        text_extraction_method="pdftext",
        polygon=PolygonBox(polygon=[[0, 30], [100, 30], [100, 50], [0, 50]], bbox=[0, 30, 100, 50]),
        html="Background"
    )
    
    # Create text content
    text1 = Text(
        block_type=BlockTypes.Text,
        block_id=3,
        page_id=0,
        text_extraction_method="pdftext",
        polygon=PolygonBox(polygon=[[0, 60], [100, 60], [100, 80], [0, 80]], bbox=[0, 60, 100, 80]),
        html="This is the introduction text explaining the document purpose."
    )
    
    text2 = Text(
        block_type=BlockTypes.Text,
        block_id=4,
        page_id=0,
        text_extraction_method="pdftext",
        polygon=PolygonBox(polygon=[[0, 90], [100, 90], [100, 110], [0, 110]], bbox=[0, 90, 100, 110]),
        html="Background information about the topic with detailed context."
    )
    
    # Structure the document
    page.children = [section1, text1, section2, text2]
    doc.pages = [page]
    
    # Initialize metadata
    section1.metadata = {}
    section2.metadata = {}
    
    return doc


class TestSectionSummarizer:
    """Test cases for unified section summarizer"""
    
    @patch('litellm.completion')
    def test_basic_summarization(self, mock_completion):
        """Test basic summarization functionality"""
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Test summary"))]
        mock_completion.return_value = mock_response
        
        # Create document and summarizer
        doc = create_test_document()
        summarizer = SectionSummarizer()
        
        # Process document
        result = summarizer(doc)
        
        # Verify sections were summarized
        sections = [block for page in result.pages 
                   for block in page.children 
                   if block.block_type == BlockTypes.SectionHeader]
        
        assert len(sections) == 2
        for section in sections:
            assert 'summary' in section.metadata
            assert section.metadata['summary'] == "Test summary"
        
        # Check document summary
        assert 'document_summary' in result.metadata
    
    def test_configuration(self):
        """Test summarizer configuration"""
        config = {
            'model_name': 'custom-model',
            'temperature': 0.5,
            'max_section_length': 2000,
            'enabled': True
        }
        
        summarizer = SectionSummarizer(config)
        
        assert summarizer.model_name == 'custom-model'
        assert summarizer.temperature == 0.5
        assert summarizer.max_section_length == 2000
        assert summarizer.enabled is True
    
    def test_disabled_summarizer(self):
        """Test disabled summarizer returns document unchanged"""
        doc = create_test_document()
        summarizer = SectionSummarizer({'enabled': False})
        
        result = summarizer(doc)
        
        # Document should be unchanged
        assert result == doc
        
        # No summaries should be added
        sections = [block for page in result.pages 
                   for block in page.children 
                   if block.block_type == BlockTypes.SectionHeader]
        
        for section in sections:
            assert 'summary' not in section.metadata
    
    @patch('litellm.completion')
    def test_error_handling(self, mock_completion):
        """Test error handling during summarization"""
        # Mock LLM error
        mock_completion.side_effect = Exception("LLM Error")
        
        doc = create_test_document()
        summarizer = SectionSummarizer()
        
        # Should not raise exception
        result = summarizer(doc)
        
        # Document should still be returned
        assert result is not None
    
    def test_section_content_extraction(self):
        """Test section content extraction logic"""
        doc = create_test_document()
        summarizer = SectionSummarizer()
        
        section = doc.pages[0].children[0]  # Introduction section
        content = summarizer._get_section_content(doc, section)
        
        assert "Introduction" in content
        assert "introduction text explaining" in content
    
    def test_empty_document(self):
        """Test handling of document with no sections"""
        doc = Document(
            filepath="empty.pdf",
            pages=[PageGroup(
                block_type=BlockTypes.PageGroup,
                block_id=0,
                page_id=0,
                polygon=PolygonBox(polygon=[[0, 0], [612, 0], [612, 792], [0, 792]], bbox=[0, 0, 612, 792]),
                children=[]
            )],
            metadata={}
        )
        
        summarizer = SectionSummarizer()
        result = summarizer(doc)
        
        assert 'document_summary' not in result.metadata
    
    @patch('litellm.completion')
    def test_long_content_truncation(self, mock_completion):
        """Test that long content is truncated"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Truncated summary"))]
        mock_completion.return_value = mock_response
        
        doc = create_test_document()
        
        # Add very long text
        long_text = Text(
            block_type=BlockTypes.Text,
            block_id=5,
            page_id=0,
            text_extraction_method="pdftext",
            polygon=PolygonBox(polygon=[[0, 120], [100, 120], [100, 140], [0, 120]], bbox=[0, 120, 100, 140]),
            html="x" * 5000  # Very long text
        )
        doc.pages[0].children.append(long_text)
        
        summarizer = SectionSummarizer({'max_section_length': 100})
        result = summarizer(doc)
        
        # Should still complete without error
        assert 'document_summary' in result.metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"])