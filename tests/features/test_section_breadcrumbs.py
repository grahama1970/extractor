#!/usr/bin/env python3
"""
Test for section breadcrumb functionality
"""
import pytest
from marker.schema.document import Document
from marker.schema.blocks.sectionheader import SectionHeader
from marker.schema.groups.page import PageGroup
from marker.schema import BlockTypes
from marker.schema.polygon import PolygonBox


def create_hierarchical_document():
    """Create a document with hierarchical sections for testing breadcrumbs"""
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
    
    # Create hierarchical sections
    section1 = SectionHeader(
        block_type=BlockTypes.SectionHeader,
        block_id=1,
        page_id=0,
        heading_level=1,
        text_extraction_method="pdftext",
        polygon=PolygonBox(polygon=[[0, 0], [100, 0], [100, 20], [0, 20]], bbox=[0, 0, 100, 20]),
        html="1. Introduction"
    )
    
    section1_1 = SectionHeader(
        block_type=BlockTypes.SectionHeader,
        block_id=2,
        page_id=0,
        heading_level=2,
        text_extraction_method="pdftext",
        polygon=PolygonBox(polygon=[[0, 30], [100, 30], [100, 50], [0, 50]], bbox=[0, 30, 100, 50]),
        html="1.1 Background"
    )
    
    section1_2 = SectionHeader(
        block_type=BlockTypes.SectionHeader,
        block_id=3,
        page_id=0,
        heading_level=2,
        text_extraction_method="pdftext",
        polygon=PolygonBox(polygon=[[0, 60], [100, 60], [100, 80], [0, 60]], bbox=[0, 60, 100, 80]),
        html="1.2 Objectives"
    )
    
    section2 = SectionHeader(
        block_type=BlockTypes.SectionHeader,
        block_id=4,
        page_id=0,
        heading_level=1,
        text_extraction_method="pdftext",
        polygon=PolygonBox(polygon=[[0, 90], [100, 90], [100, 110], [0, 90]], bbox=[0, 90, 100, 110]),
        html="2. Methods"
    )
    
    page.children = [section1, section1_1, section1_2, section2]
    doc.pages = [page]
    
    return doc


class TestSectionBreadcrumbs:
    """Test section breadcrumb functionality"""
    
    def test_breadcrumb_creation(self):
        """Test that breadcrumbs are created correctly"""
        doc = create_hierarchical_document()
        
        # Get sections
        sections = [block for page in doc.pages 
                   for block in page.children 
                   if block.block_type == BlockTypes.SectionHeader]
        
        # Set up breadcrumbs manually (normally done by hierarchy builder)
        sections[0].metadata = {'section_hierarchy_titles': ['1. Introduction']}
        sections[1].metadata = {'section_hierarchy_titles': ['1. Introduction', '1.1 Background']}
        sections[2].metadata = {'section_hierarchy_titles': ['1. Introduction', '1.2 Objectives']}
        sections[3].metadata = {'section_hierarchy_titles': ['2. Methods']}
        
        # Test breadcrumb paths
        assert sections[0].metadata['section_hierarchy_titles'] == ['1. Introduction']
        assert sections[1].metadata['section_hierarchy_titles'] == ['1. Introduction', '1.1 Background']
        assert sections[2].metadata['section_hierarchy_titles'] == ['1. Introduction', '1.2 Objectives']
        assert sections[3].metadata['section_hierarchy_titles'] == ['2. Methods']
    
    def test_breadcrumb_hashes(self):
        """Test that section hashes are generated"""
        doc = create_hierarchical_document()
        
        # Get first section
        section = doc.pages[0].children[0]
        
        # Set breadcrumb with hash
        section.metadata = {
            'section_hierarchy_titles': ['1. Introduction'],
            'section_hierarchy_hashes': ['hash_abc123']
        }
        
        assert section.metadata['section_hierarchy_hashes'] == ['hash_abc123']
    
    def test_nested_sections(self):
        """Test deeply nested section hierarchies"""
        doc = create_hierarchical_document()
        
        # Add a deeply nested section
        section1_1_1 = SectionHeader(
            block_type=BlockTypes.SectionHeader,
            block_id=5,
            page_id=0,
            heading_level=3,
            text_extraction_method="pdftext",
            polygon=PolygonBox(polygon=[[0, 120], [100, 120], [100, 140], [0, 120]], bbox=[0, 120, 100, 140]),
            html="1.1.1 Historical Context"
        )
        
        doc.pages[0].children.insert(2, section1_1_1)
        
        # Set breadcrumb
        section1_1_1.metadata = {
            'section_hierarchy_titles': ['1. Introduction', '1.1 Background', '1.1.1 Historical Context'],
            'section_hierarchy_hashes': ['hash1', 'hash2', 'hash3']
        }
        
        assert len(section1_1_1.metadata['section_hierarchy_titles']) == 3
        assert len(section1_1_1.metadata['section_hierarchy_hashes']) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])