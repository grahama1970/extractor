"""
Hierarchical JSON renderer that outputs the enhanced document structure
"""
from typing import Dict, List, Any
from marker.renderers import BaseRenderer
from marker.schema.document import Document
from marker.schema.enhanced_document import HierarchicalDocument, Section
import json

class HierarchicalJSONRenderer(BaseRenderer):
    """
    Renderer that outputs the hierarchical document structure as JSON
    """
    
    def __call__(self, document: Document) -> str:
        """Render document to hierarchical JSON"""
        if (hasattr(document, 'metadata') and 
            'hierarchical_structure' in document.metadata):
            hierarchical_doc = document.metadata['hierarchical_structure']
            return self._render_hierarchical(hierarchical_doc)
        else:
            # Fallback to standard rendering
            return self._render_flat(document)
    
    def _render_hierarchical(self, hierarchical_doc: HierarchicalDocument) -> str:
        """Render the hierarchical document structure"""
        output = {
            "file_metadata": hierarchical_doc.file_metadata.model_dump(),
            "processing_metadata": hierarchical_doc.processing_metadata.model_dump(),
            "document_metadata": hierarchical_doc.document_metadata.model_dump(),
            "table_of_contents": hierarchical_doc.table_of_contents,
            "sections": [
                self._render_section(section) 
                for section in hierarchical_doc.sections
            ]
        }
        
        return json.dumps(output, indent=2, default=str)
    
    def _render_section(self, section: Section) -> Dict[str, Any]:
        """Render a section and its content"""
        return {
            "id": section.id,
            "section_hash": section.section_hash,
            "header": {
                "text": section.header.html or "",
                "page_id": section.header.page_id,
                "heading_level": section.header.heading_level,
                "bbox": section.header.polygon.bbox if section.header.polygon else None
            },
            "metadata": {
                "summary": section.metadata.summary,
                "section_number": section.metadata.section_number,
                "depth_level": section.metadata.depth_level,
                "hierarchy_titles": section.metadata.hierarchy_titles,
                "hierarchy_hashes": section.metadata.hierarchy_hashes,
                "word_count": section.metadata.word_count,
                "content_types": {
                    "has_images": section.metadata.has_images,
                    "has_tables": section.metadata.has_tables,
                    "has_equations": section.metadata.has_equations,
                    "has_code": section.metadata.has_code
                },
                "counts": {
                    "text_blocks": section.metadata.text_block_count,
                    "images": section.metadata.image_count,
                    "tables": section.metadata.table_count
                }
            },
            "content_blocks": [
                self._render_block(block)
                for block in section.content_blocks
            ],
            "subsections": [
                self._render_section(subsection)
                for subsection in section.subsections
            ]
        }
    
    def _render_block(self, block) -> Dict[str, Any]:
        """Render a content block"""
        block_data = {
            "id": str(block.id) if hasattr(block, 'id') else None,
            "type": str(block.block_type),
            "page_id": block.page_id,
            "bbox": block.polygon.bbox if hasattr(block, 'polygon') and block.polygon else None,
        }
        
        # Add content based on block type
        if hasattr(block, 'html') and block.html:
            block_data["html"] = block.html
        elif hasattr(block, 'text') and block.text:
            block_data["text"] = block.text
        
        # Add table data if it's a table
        if hasattr(block, 'table_data'):
            block_data["table_data"] = block.table_data
        
        # Add image info if it's an image
        if hasattr(block, 'image_path'):
            block_data["image_path"] = block.image_path
        
        # Add any additional metadata
        if hasattr(block, 'metadata') and block.metadata:
            block_data["metadata"] = block.metadata
        
        return block_data
    
    def _render_flat(self, document: Document) -> str:
        """Fallback flat rendering"""
        # Standard JSON rendering
        return json.dumps({
            "filepath": document.filepath,
            "pages": [
                {
                    "page_id": page.page_id,
                    "children": [
                        self._render_block(block)
                        for block in page.children
                    ]
                }
                for page in document.pages
            ],
            "metadata": document.metadata if hasattr(document, 'metadata') else {}
        }, indent=2, default=str)

class CompactHierarchicalJSONRenderer(HierarchicalJSONRenderer):
    """
    Compact version that only includes essential information
    """
    
    def _render_section(self, section: Section) -> Dict[str, Any]:
        """Render a section in compact format"""
        return {
            "title": section.header.html or "",
            "number": section.metadata.section_number,
            "hierarchy": section.metadata.hierarchy_titles,
            "summary": section.metadata.summary,
            "content_count": len(section.content_blocks),
            "subsections": [
                self._render_section(subsection)
                for subsection in section.subsections
            ]
        }
    
    def _render_hierarchical(self, hierarchical_doc: HierarchicalDocument) -> str:
        """Render compact hierarchical structure"""
        output = {
            "title": hierarchical_doc.document_metadata.title,
            "summary": hierarchical_doc.document_metadata.document_summary,
            "stats": {
                "pages": hierarchical_doc.document_metadata.page_count,
                "sections": hierarchical_doc.document_metadata.total_sections,
                "words": hierarchical_doc.document_metadata.total_words,
                "reading_time": hierarchical_doc.document_metadata.estimated_reading_time
            },
            "sections": [
                self._render_section(section)
                for section in hierarchical_doc.sections
            ]
        }
        
        return json.dumps(output, indent=2, default=str)