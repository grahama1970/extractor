#!/usr/bin/env python
"""
Add section breadcrumbs to marker document objects based on section hierarchy.
This script enhances each block with section context and breadcrumb navigation.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from marker.schema.document import Document
from marker.schema.blocks import Block
from marker.schema import BlockTypes
from marker.schema.blocks.sectionheader import SectionHeader

# Add marker to path
sys.path.insert(0, str(Path(__file__).parent))

class SectionBreadcrumbEnhancer:
    """
    Enhances document blocks with section hierarchy and breadcrumb information.
    """
    
    def __init__(self):
        self.current_breadcrumb = []
        self.current_section_ids = []
        
    def enhance_document_with_breadcrumbs(self, document: Document) -> List[Dict[str, Any]]:
        """
        Process a document and add breadcrumb information to each block.
        
        Args:
            document: The marker Document object
            
        Returns:
            List of enhanced block dictionaries with breadcrumb information
        """
        enhanced_blocks = []
        
        # Process each page in the document
        for page in document.pages:
            # Get all blocks from the page in order
            blocks = list(page.children)
            
            for block in blocks:
                # Convert block to dictionary representation
                block_dict = self._block_to_dict(block, page.page_id)
                
                # Update breadcrumb if this is a section header
                if isinstance(block, SectionHeader) or block.block_type == BlockTypes.SectionHeader:
                    self._update_breadcrumb(block, block_dict)
                
                # Add current breadcrumb to the block
                block_dict['section_breadcrumb'] = self.current_breadcrumb.copy()
                block_dict['section_path'] = " > ".join(self.current_breadcrumb)
                block_dict['section_level'] = len(self.current_breadcrumb)
                
                # Add section IDs for navigation
                block_dict['parent_sections'] = self.current_section_ids.copy()
                
                enhanced_blocks.append(block_dict)
                
        return enhanced_blocks
    
    def _block_to_dict(self, block: Block, page_num: int) -> Dict[str, Any]:
        """
        Convert a block to a dictionary representation.
        
        Args:
            block: The block to convert
            page_num: The page number
            
        Returns:
            Dictionary representation of the block
        """
        # Basic block information
        block_dict = {
            'type': block.block_type.value if hasattr(block.block_type, 'value') else str(block.block_type),
            'id': block.id,
            'page': page_num,
            'bbox': block.polygon.bbox if hasattr(block, 'polygon') and block.polygon else None,
        }
        
        # Add text content
        if hasattr(block, 'text'):
            block_dict['text'] = block.text
        elif hasattr(block, 'text_lines') and block.text_lines:
            block_dict['text'] = ' '.join(block.text_lines)
        
        # Add level for section headers
        if isinstance(block, SectionHeader) or block.block_type == BlockTypes.SectionHeader:
            if hasattr(block, 'level'):
                block_dict['level'] = block.level
        
        # Add any additional metadata
        if hasattr(block, 'metadata') and block.metadata:
            block_dict['metadata'] = block.metadata
            
        return block_dict
    
    def _update_breadcrumb(self, block: Block, block_dict: Dict[str, Any]):
        """
        Update the current breadcrumb based on a section header.
        
        Args:
            block: The section header block
            block_dict: Dictionary representation of the block
        """
        # Get the section level
        level = getattr(block, 'level', 1)
        if 'level' in block_dict:
            level = block_dict['level']
        
        # Get the section text
        section_text = block_dict.get('text', 'Section')
        
        # Update breadcrumb based on level
        # Level 1 replaces everything
        if level == 1:
            self.current_breadcrumb = [section_text]
            self.current_section_ids = [block.id]
        # Higher levels update the breadcrumb at that level
        else:
            # Ensure we have enough levels in the breadcrumb
            while len(self.current_breadcrumb) < level - 1:
                self.current_breadcrumb.append("")
                self.current_section_ids.append("")
            
            # Trim if we have too many levels
            if len(self.current_breadcrumb) >= level:
                self.current_breadcrumb = self.current_breadcrumb[:level-1]
                self.current_section_ids = self.current_section_ids[:level-1]
            
            # Add the new level
            self.current_breadcrumb.append(section_text)
            self.current_section_ids.append(block.id)


def add_breadcrumbs_to_document(document: Document) -> List[Dict[str, Any]]:
    """
    Main function to add breadcrumbs to a document.
    
    Args:
        document: The marker Document object
        
    Returns:
        List of enhanced block dictionaries
    """
    enhancer = SectionBreadcrumbEnhancer()
    return enhancer.enhance_document_with_breadcrumbs(document)


# Example usage and testing
if __name__ == "__main__":
    # Create a sample document for testing
    from marker.schema.polygon import PolygonBox
    from marker.schema.groups.page import Page
    from marker.schema.blocks.text import Text
    
    print("=== Section Breadcrumb Enhancement Demo ===\n")
    
    # Create a mock document
    document = Document(filepath="test.pdf", pages=[])
    
    # Create a page
    page = Page(page_id=0, polygon=PolygonBox(polygon=[[0, 0], [595, 0], [595, 842], [0, 842]]))
    
    # Create sample blocks
    title_block = Text(
        id="title1",
        polygon=PolygonBox(polygon=[[50, 50], [545, 50], [545, 100], [50, 100]]),
        text_lines=["Main Document Title"]
    )
    title_block.block_type = BlockTypes.Title
    
    section1 = SectionHeader(
        id="section1",
        polygon=PolygonBox(polygon=[[50, 150], [545, 150], [545, 200], [50, 200]]),
        text_lines=["Introduction"],
        level=1
    )
    
    text1 = Text(
        id="text1",
        polygon=PolygonBox(polygon=[[50, 220], [545, 220], [545, 300], [50, 300]]),
        text_lines=["This is the introduction text."]
    )
    
    section2 = SectionHeader(
        id="section2",
        polygon=PolygonBox(polygon=[[50, 350], [545, 350], [545, 400], [50, 400]]),
        text_lines=["Methods"],
        level=1
    )
    
    section2_1 = SectionHeader(
        id="section2_1",
        polygon=PolygonBox(polygon=[[50, 420], [545, 420], [545, 470], [50, 470]]),
        text_lines=["Data Collection"],
        level=2
    )
    
    text2 = Text(
        id="text2",
        polygon=PolygonBox(polygon=[[50, 490], [545, 490], [545, 570], [50, 570]]),
        text_lines=["Description of data collection methods."]
    )
    
    # Add blocks to page
    page.children = [title_block, section1, text1, section2, section2_1, text2]
    document.pages.append(page)
    
    # Process document with breadcrumbs
    enhanced_blocks = add_breadcrumbs_to_document(document)
    
    # Display results
    print("Enhanced Document Structure with Breadcrumbs:\n")
    for i, block in enumerate(enhanced_blocks):
        print(f"Block {i + 1}:")
        print(f"  Type: {block['type']}")
        print(f"  Text: {block.get('text', 'N/A')}")
        print(f"  Page: {block['page']}")
        print(f"  Section Path: {block['section_path']}")
        print(f"  Section Level: {block['section_level']}")
        print(f"  Parent Sections: {block['parent_sections']}")
        print()
    
    # Output as JSON-like structure
    import json
    print("\nJSON Output:")
    json_output = []
    for block in enhanced_blocks:
        json_block = {
            "type": block['type'],
            "text": block.get('text', ''),
            "page": block['page'],
            "section_path": block['section_path'],
            "section_level": block['section_level']
        }
        json_output.append(json_block)
    
    print(json.dumps(json_output, indent=2))