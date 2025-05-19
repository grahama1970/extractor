#!/usr/bin/env python3
"""
Test the hierarchical document structure
"""
from marker.schema.document import Document
from marker.schema.blocks.sectionheader import SectionHeader
from marker.schema.blocks.text import Text
from marker.schema.blocks.table import Table
from marker.schema.blocks.picture import Picture
from marker.schema.groups.page import PageGroup
from marker.schema import BlockTypes
from marker.schema.polygon import PolygonBox
from marker.processors.hierarchy_builder import HierarchyBuilder
from marker.renderers.hierarchical_json import HierarchicalJSONRenderer
import json

def create_test_document():
    """Create a test document with mixed content"""
    doc = Document(
        filepath="test_document.pdf",
        pages=[],
        metadata={}
    )
    
    # Page 1
    page1 = PageGroup(
        block_type=BlockTypes.Page,
        block_id=0,
        page_id=0,
        text_extraction_method="pdftext",
        polygon=PolygonBox(polygon=[[0, 0], [612, 0], [612, 792], [0, 792]]),
        children=[]
    )
    
    # Section 1: Introduction
    section1 = SectionHeader(
        block_type=BlockTypes.SectionHeader,
        block_id=1,
        page_id=0,
        heading_level=1,
        html="1. Introduction",
        text_extraction_method="pdftext",
        polygon=PolygonBox(polygon=[[50, 50], [500, 50], [500, 70], [50, 70]]),
    )
    page1.children.append(section1)
    
    # Text block 1
    text1 = Text(
        block_type=BlockTypes.Text,
        block_id=2,
        page_id=0,
        html="This document demonstrates the hierarchical structure with mixed content types.",
        text_extraction_method="pdftext",
        polygon=PolygonBox(polygon=[[50, 80], [500, 80], [500, 100], [50, 100]]),
    )
    page1.children.append(text1)
    
    # Image 1
    image1 = Picture(
        block_type=BlockTypes.Picture,
        block_id=3,
        page_id=0,
        text_extraction_method="pdftext",
        polygon=PolygonBox(polygon=[[50, 110], [300, 110], [300, 250], [50, 250]]),
    )
    page1.children.append(image1)
    
    # Text block 2
    text2 = Text(
        block_type=BlockTypes.Text,
        block_id=4,
        page_id=0,
        html="The image above shows the system architecture.",
        text_extraction_method="pdftext",
        polygon=PolygonBox(polygon=[[50, 260], [500, 260], [500, 280], [50, 280]]),
    )
    page1.children.append(text2)
    
    # Section 1.1: Background
    section1_1 = SectionHeader(
        block_type=BlockTypes.SectionHeader,
        block_id=5,
        page_id=0,
        heading_level=2,
        html="1.1 Background",
        text_extraction_method="pdftext",
        polygon=PolygonBox(polygon=[[50, 300], [500, 300], [500, 320], [50, 320]]),
    )
    page1.children.append(section1_1)
    
    # Text in subsection
    text3 = Text(
        block_type=BlockTypes.Text,
        block_id=6,
        page_id=0,
        html="This subsection provides background information about the topic.",
        text_extraction_method="pdftext",
        polygon=PolygonBox(polygon=[[50, 330], [500, 330], [500, 350], [50, 350]]),
    )
    page1.children.append(text3)
    
    # Table in subsection
    table1 = Table(
        block_type=BlockTypes.Table,
        block_id=7,
        page_id=0,
        text_extraction_method="pdftext",
        polygon=PolygonBox(polygon=[[50, 360], [500, 360], [500, 450], [50, 450]]),
        table_data=[
            ["Year", "Value", "Growth"],
            ["2020", "100", "5%"],
            ["2021", "105", "5%"],
            ["2022", "110", "4.8%"]
        ]
    )
    page1.children.append(table1)
    
    # Text after table
    text4 = Text(
        block_type=BlockTypes.Text,
        block_id=8,
        page_id=0,
        html="The table shows steady growth over the years.",
        text_extraction_method="pdftext",
        polygon=PolygonBox(polygon=[[50, 460], [500, 460], [500, 480], [50, 480]]),
    )
    page1.children.append(text4)
    
    # Section 2: Methods
    section2 = SectionHeader(
        block_type=BlockTypes.SectionHeader,
        block_id=9,
        page_id=0,
        heading_level=1,
        html="2. Methods",
        text_extraction_method="pdftext",
        polygon=PolygonBox(polygon=[[50, 500], [500, 500], [500, 520], [50, 520]]),
    )
    page1.children.append(section2)
    
    # Text in section 2
    text5 = Text(
        block_type=BlockTypes.Text,
        block_id=10,
        page_id=0,
        html="This section describes the methodology used in our research.",
        text_extraction_method="pdftext",
        polygon=PolygonBox(polygon=[[50, 530], [500, 530], [500, 550], [50, 550]]),
    )
    page1.children.append(text5)
    
    doc.pages.append(page1)
    
    # Add test summaries
    doc.metadata = {
        'section_summaries': [
            {
                'section_id': '/page/0/SectionHeader/1',
                'title': '1. Introduction',
                'summary': 'Introduction section demonstrating mixed content types including text and images.'
            },
            {
                'section_id': '/page/0/SectionHeader/5',
                'title': '1.1 Background',
                'summary': 'Background subsection containing text and tabular data showing growth trends.'
            },
            {
                'section_id': '/page/0/SectionHeader/9',
                'title': '2. Methods',
                'summary': 'Methods section describing the research methodology.'
            }
        ],
        'document_summary': 'A test document demonstrating hierarchical structure with sections, subsections, and mixed content types including text, images, and tables.'
    }
    
    return doc

def main():
    print("Creating test document...")
    doc = create_test_document()
    
    print("\nBuilding hierarchical structure...")
    hierarchy_builder = HierarchyBuilder()
    doc = hierarchy_builder(doc)
    
    print("\nRendering hierarchical JSON...")
    renderer = HierarchicalJSONRenderer()
    json_output = renderer(doc)
    
    # Pretty print the output
    output_data = json.loads(json_output)
    
    print("\n" + "="*50)
    print("HIERARCHICAL DOCUMENT STRUCTURE")
    print("="*50)
    
    # Show document metadata
    print("\nDocument Metadata:")
    print(f"  File: {output_data['file_metadata']['filepath']}")
    print(f"  Pages: {output_data['document_metadata']['page_count']}")
    print(f"  Sections: {output_data['document_metadata']['total_sections']}")
    
    # Show table of contents
    print("\nTable of Contents:")
    for item in output_data['table_of_contents']:
        indent = "  " * item['depth_level']
        print(f"{indent}{item['section_number']} {item['title']}")
        if 'hierarchy' in item:
            print(f"{indent}  Hierarchy: {' > '.join(item['hierarchy'])}")
    
    # Show sections with content
    print("\n" + "-"*50)
    print("SECTION DETAILS")
    print("-"*50)
    
    def print_section(section, indent_level=0):
        indent = "  " * indent_level
        print(f"\n{indent}Section {section['metadata']['section_number']}: {section['header']['text']}")
        print(f"{indent}  Hash: {section['section_hash']}")
        print(f"{indent}  Hierarchy: {' > '.join(section['metadata']['hierarchy_titles'])}")
        print(f"{indent}  Summary: {section['metadata']['summary']}")
        print(f"{indent}  Content blocks: {len(section['content_blocks'])}")
        
        # Show content blocks with preserved order
        for i, block in enumerate(section['content_blocks']):
            print(f"{indent}    {i+1}. {block['type']}: {block.get('html', block.get('text', ''))[:50]}...")
        
        # Show subsections
        for subsection in section['subsections']:
            print_section(subsection, indent_level + 1)
    
    for section in output_data['sections']:
        print_section(section)
    
    # Save full output
    with open('hierarchical_output.json', 'w') as f:
        json.dump(output_data, f, indent=2)
    print("\n\nFull output saved to hierarchical_output.json")

if __name__ == "__main__":
    main()