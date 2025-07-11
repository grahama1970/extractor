"""
Module: hierarchical_json.py
Description: Hierarchical JSON renderer that outputs the enhanced document structure
"""

import json
from typing import Dict, Any, List

from extractor.core.renderers import BaseRenderer
from extractor.core.schema.document import Document
from extractor.core.schema.enhanced_document import HierarchicalDocument, Section


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
            "document_metadata": hierarchical_doc.document_metadata.model_dump() if hierarchical_doc.document_metadata else {},
            "sections": [self._render_section(section) for section in hierarchical_doc.sections],
            "processing_metadata": hierarchical_doc.processing_metadata.model_dump()
        }
        return json.dumps(output, indent=2, default=str)
    
    def _render_section(self, section: Section) -> Dict[str, Any]:
        """Render a section and its subsections"""
        return {
            "id": section.id,
            "title": section.title,
            "level": section.level,
            "parent_id": section.parent_id,
            "page_range": list(section.page_range) if section.page_range else [],
            "blocks": [self._render_block(block) for block in section.blocks],
            "metadata": section.metadata.model_dump() if section.metadata else {},
            "subsections": [self._render_section(subsection) for subsection in section.subsections]
        }
    
    def _render_block(self, block) -> Dict[str, Any]:
        """Render a block to dict"""
        return {
            "type": block.block_type,
            "text": getattr(block, 'text', ''),
            "page_id": getattr(block, 'page_id', None),
            "metadata": block.metadata if hasattr(block, 'metadata') else {}
        }
    
    def _render_flat(self, document: Document) -> str:
        """Fallback flat rendering"""
        return json.dumps({
            "pages": [
                {
                    "page_id": page.page_id,
                    "blocks": [
                        {
                            "type": block.block_type,
                            "text": getattr(block, 'text', ''),
                            "metadata": block.metadata if hasattr(block, 'metadata') else {}
                        }
                        for block in page.blocks
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
        """Render section without metadata for compact output"""
        return {
            "id": section.id,
            "title": section.title,
            "level": section.level,
            "blocks": [block.block_type for block in section.blocks],
            "subsections": [self._render_section(subsection) for subsection in section.subsections]
        }


if __name__ == "__main__":
    """Validation test"""
    print("✅ HierarchicalJSONRenderer module loaded successfully")