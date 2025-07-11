"""
Enhanced ArangoDB renderer with relationship extraction and graph structure support.
Module: arangodb_enhanced.py
Description: Implementation of arangodb enhanced functionality

This renderer creates JSON documents optimized for ArangoDB's graph database capabilities,
including automatic relationship extraction, entity detection, and hierarchical structure.

Links:
- ArangoDB Python driver: https://pyarango.readthedocs.io/
- Task details: docs/tasks/032_ArangoDB_Marker_Integration.md

Sample Input:
    Document object with pages, blocks, and metadata

Expected Output:
{
    "vertices": {
        "documents": [...],
        "sections": [...],
        "entities": [...]
    },
    "edges": {
        "contains": [...],
        "references": [...],
        "relates_to": [...]
    }
}
"""

import json
import re
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

from loguru import logger

from extractor.core.renderers import BaseRenderer
from extractor.core.schema.document import Document
from extractor.core.schema.blocks.base import Block
from extractor.core.utils.arangodb_validator import ArangoDBDocumentValidator


class ArangoDBEnhancedRenderer(BaseRenderer):
    """
    Enhanced ArangoDB renderer that produces graph-ready JSON with relationships.
    
    Features:
    - Automatic entity extraction (people, organizations, locations)
    - Section hierarchy with parent-child relationships
    - Cross-reference detection
    - Table relationship mapping
    - Performance metrics tracking
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.config = config or {}
        self.extract_entities = self.config.get("extract_entities", True)
        self.extract_relationships = self.config.get("extract_relationships", True)
        self.include_embeddings = self.config.get("include_embeddings", False)
    
    def __call__(self, document: Document) -> str:
        """
        Render document to ArangoDB graph-ready JSON.
        
        Args:
            document: The document to render
            
        Returns:
            JSON string with vertices and edges
        """
        start_time = datetime.now()
        
        # Extract graph structure
        graph_data = self._extract_graph_structure(document)
        
        # Add metadata
        graph_data["metadata"] = {
            "source_file": getattr(document, "filepath", "unknown"),
            "processing_time": (datetime.now() - start_time).total_seconds(),
            "renderer_version": "2.0",
            "extraction_config": {
                "entities": self.extract_entities,
                "relationships": self.extract_relationships,
                "embeddings": self.include_embeddings
            }
        }
        
        return json.dumps(graph_data, indent=2, ensure_ascii=False)
    
    def _extract_graph_structure(self, document: Document) -> Dict[str, Any]:
        """Extract vertices and edges from document."""
        vertices = {
            "documents": [],
            "sections": [],
            "blocks": [],
            "entities": [],
            "tables": []
        }
        
        edges = {
            "contains": [],      # Document -> Section -> Block
            "references": [],    # Block -> Entity
            "follows": [],       # Block -> Block (sequential)
            "relates_to": []     # Entity -> Entity
        }
        
        # Create document vertex
        doc_id = self._generate_id("doc", document.filepath if hasattr(document, 'filepath') else "unknown")
        doc_vertex = {
            "_key": doc_id,
            "_id": f"documents/{doc_id}",
            "type": "document",
            "title": self._extract_title(document),
            "page_count": len(document.pages),
            "created_at": datetime.now().isoformat()
        }
        vertices["documents"].append(doc_vertex)
        
        # Process pages and blocks
        section_stack = []  # Track section hierarchy
        prev_block_id = None
        
        for page_idx, page in enumerate(document.pages):
            for block_idx, block in enumerate(page.blocks):
                block_id = self._generate_id("block", f"{page_idx}_{block_idx}")
                
                # Create block vertex
                block_vertex = {
                    "_key": block_id,
                    "_id": f"blocks/{block_id}",
                    "type": block.block_type,
                    "page": page_idx,
                    "position": block_idx,
                    "text": self._get_block_text(block),
                    "bbox": block.bbox if hasattr(block, 'bbox') else None
                }
                vertices["blocks"].append(block_vertex)
                
                # Handle sections
                if block.block_type == "SectionHeader":
                    section_id = self._create_section(block, vertices, edges, doc_id, section_stack)
                    # Create contains edge: section -> block
                    edges["contains"].append({
                        "_from": f"sections/{section_id}",
                        "_to": f"blocks/{block_id}",
                        "type": "section_contains_block"
                    })
                elif section_stack:
                    # Add block to current section
                    edges["contains"].append({
                        "_from": f"sections/{section_stack[-1]['id']}",
                        "_to": f"blocks/{block_id}",
                        "type": "section_contains_block"
                    })
                else:
                    # Add block directly to document
                    edges["contains"].append({
                        "_from": f"documents/{doc_id}",
                        "_to": f"blocks/{block_id}",
                        "type": "document_contains_block"
                    })
                
                # Create sequential edges
                if prev_block_id:
                    edges["follows"].append({
                        "_from": f"blocks/{prev_block_id}",
                        "_to": f"blocks/{block_id}",
                        "type": "sequential"
                    })
                prev_block_id = block_id
                
                # Extract entities from block
                if self.extract_entities:
                    self._extract_entities_from_block(block, block_id, vertices, edges)
                
                # Handle tables specially
                if block.block_type == "Table":
                    self._process_table(block, block_id, vertices, edges)
        
        # Extract relationships between entities
        if self.extract_relationships:
            self._extract_entity_relationships(vertices["entities"], edges)
        
        # Validate all documents before returning
        validator = ArangoDBDocumentValidator()
        validation_errors = []
        
        # Validate vertices
        for collection, docs in vertices.items():
            for doc in docs:
                is_valid, errors = validator.validate_document(doc)
                if not is_valid:
                    validation_errors.extend([f"{collection}/{doc.get('_key', 'unknown')}: {e}" for e in errors])
        
        # Validate edges
        for edge_type, edge_list in edges.items():
            for edge in edge_list:
                is_valid, errors = validator.validate_document(edge)
                if not is_valid:
                    validation_errors.extend([f"{edge_type}: {e}" for e in errors])
        
        result = {"vertices": vertices, "edges": edges}
        
        if validation_errors:
            result["validation_warnings"] = validation_errors
            logger.warning(f"ArangoDB document validation found {len(validation_errors)} issues")
        
        return result
    
    def _create_section(self, header_block: Block, vertices: Dict, edges: Dict, 
                       doc_id: str, section_stack: List[Dict]) -> str:
        """Create section vertex and manage hierarchy."""
        section_id = self._generate_id("section", header_block.text)
        level = getattr(header_block, 'level', 1)
        
        # Pop sections from stack until we find parent
        while section_stack and section_stack[-1]['level'] >= level:
            section_stack.pop()
        
        section_vertex = {
            "_key": section_id,
            "_id": f"sections/{section_id}",
            "title": header_block.text,
            "level": level,
            "type": "section"
        }
        vertices["sections"].append(section_vertex)
        
        # Create hierarchy edge
        if section_stack:
            # Child of another section
            edges["contains"].append({
                "_from": f"sections/{section_stack[-1]['id']}",
                "_to": f"sections/{section_id}",
                "type": "section_contains_section"
            })
        else:
            # Top-level section
            edges["contains"].append({
                "_from": f"documents/{doc_id}",
                "_to": f"sections/{section_id}",
                "type": "document_contains_section"
            })
        
        # Add to stack
        section_stack.append({"id": section_id, "level": level})
        
        return section_id
    
    def _extract_entities_from_block(self, block: Block, block_id: str, 
                                   vertices: Dict, edges: Dict):
        """Extract named entities from block text."""
        text = self._get_block_text(block)
        if not text:
            return
        
        # Simple regex patterns for demonstration
        # In production, use spaCy or similar NLP library
        patterns = {
            "person": r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',
            "organization": r'\b(?:Inc\.|LLC|Corp\.|Company|University|Institute)\b',
            "location": r'\b(?:New York|London|Paris|Tokyo|[A-Z][a-z]+ City)\b',
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "url": r'https?://[^\s]+',
            "date": r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'
        }
        
        for entity_type, pattern in patterns.items():
            for match in re.finditer(pattern, text):
                entity_text = match.group()
                entity_id = self._generate_id("entity", f"{entity_type}_{entity_text}")
                
                # Check if entity already exists
                if not any(e["_key"] == entity_id for e in vertices["entities"]):
                    vertices["entities"].append({
                        "_key": entity_id,
                        "_id": f"entities/{entity_id}",
                        "type": entity_type,
                        "value": entity_text,
                        "normalized": entity_text.lower()
                    })
                
                # Create reference edge
                edges["references"].append({
                    "_from": f"blocks/{block_id}",
                    "_to": f"entities/{entity_id}",
                    "type": "mentions",
                    "position": match.start()
                })
    
    def _process_table(self, table_block: Block, block_id: str, 
                      vertices: Dict, edges: Dict):
        """Process table block and extract structure."""
        table_id = self._generate_id("table", block_id)
        
        table_vertex = {
            "_key": table_id,
            "_id": f"tables/{table_id}",
            "type": "table",
            "rows": len(getattr(table_block, 'cells', [])),
            "columns": len(getattr(table_block, 'cells', [[]])[0]) if hasattr(table_block, 'cells') else 0,
            "headers": self._extract_table_headers(table_block)
        }
        vertices["tables"].append(table_vertex)
        
        # Link table to block
        edges["contains"].append({
            "_from": f"blocks/{block_id}",
            "_to": f"tables/{table_id}",
            "type": "block_contains_table"
        })
    
    def _extract_entity_relationships(self, entities: List[Dict], edges: Dict):
        """Extract relationships between entities based on co-occurrence."""
        # Simple co-occurrence based relationship extraction
        # In production, use more sophisticated NLP techniques
        
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i+1:]:
                # Create relationship if entities are of different types
                if entity1["type"] != entity2["type"]:
                    edges["relates_to"].append({
                        "_from": f"entities/{entity1['_key']}",
                        "_to": f"entities/{entity2['_key']}",
                        "type": "co_occurs",
                        "weight": 1.0
                    })
    
    def _extract_title(self, document: Document) -> str:
        """Extract document title from first heading or metadata."""
        # Check metadata first
        if hasattr(document, 'metadata') and 'title' in document.metadata:
            return document.metadata['title']
        
        # Look for first heading
        for page in document.pages:
            for block in page.blocks:
                if block.block_type == "SectionHeader":
                    return block.text
        
        return "Untitled Document"
    
    def _get_block_text(self, block: Block) -> str:
        """Safely extract text from block."""
        if hasattr(block, 'text'):
            return block.text
        elif hasattr(block, 'caption'):
            return block.caption
        return ""
    
    def _extract_table_headers(self, table_block: Block) -> List[str]:
        """Extract headers from table block."""
        if hasattr(table_block, 'cells') and table_block.cells:
            return [str(cell) for cell in table_block.cells[0]]
        return []
    
    def _generate_id(self, prefix: str, content: str) -> str:
        """Generate stable ID from content that is ArangoDB compliant."""
        # Use hash for stable IDs
        hash_input = f"{prefix}_{content}".encode('utf-8')
        raw_id = f"{prefix}_{hashlib.md5(hash_input).hexdigest()[:12]}"
        
        # Sanitize for ArangoDB compliance
        # Replace spaces and invalid characters
        sanitized_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', raw_id)
        
        # Ensure it doesn't exceed max length (leave room for collection prefix)
        if len(sanitized_id) > 200:
            sanitized_id = sanitized_id[:200]
            
        # Validate the ID
        validator = ArangoDBDocumentValidator()
        is_valid, error = validator.validate_document_id(sanitized_id)
        if not is_valid:
            logger.warning(f"Generated ID '{sanitized_id}' is invalid: {error}")
            # Fallback to a simple hash
            sanitized_id = f"{prefix}_{hashlib.md5(content.encode()).hexdigest()[:8]}"
            
        return sanitized_id


# Validation and testing
if __name__ == "__main__":
    from extractor.core.schema.document import Document
    from extractor.core.schema.groups.page import PageGroup
    from extractor.core.schema.blocks.sectionheader import SectionHeader
    from extractor.core.schema.blocks.text import TextBlock
    from extractor.core.schema.blocks.table import Table
    
    # Create test document
    doc = Document(
        filepath="test_document.pdf",
        pages=[
            PageGroup(
                blocks=[
                    SectionHeader(
                        text="Introduction",
                        level=1,
                        bbox=[0, 0, 100, 20]
                    ),
                    TextBlock(
                        text="This document discusses John Smith from New York University.",
                        bbox=[0, 30, 100, 50]
                    ),
                    SectionHeader(
                        text="Data Analysis",
                        level=1,
                        bbox=[0, 60, 100, 80]
                    ),
                    Table(
                        cells=[
                            ["Name", "Age", "City"],
                            ["John Smith", "30", "New York"],
                            ["Jane Doe", "25", "London"]
                        ],
                        bbox=[0, 90, 100, 150]
                    ),
                    TextBlock(
                        text="Contact: john.smith@university.edu or visit https://example.com",
                        bbox=[0, 160, 100, 180]
                    )
                ],
                page_id=0
            )
        ]
    )
    
    # Test renderer
    renderer = ArangoDBEnhancedRenderer({
        "extract_entities": True,
        "extract_relationships": True
    })
    
    result = renderer(doc)
    print("ArangoDB Enhanced Renderer Output:")
    print(result)
    
    # Parse and validate
    data = json.loads(result)
    print(f"\nExtracted:")
    print(f"- Documents: {len(data['vertices']['documents'])}")
    print(f"- Sections: {len(data['vertices']['sections'])}")
    print(f"- Blocks: {len(data['vertices']['blocks'])}")
    print(f"- Entities: {len(data['vertices']['entities'])}")
    print(f"- Tables: {len(data['vertices']['tables'])}")
    print(f"\nRelationships:")
    for edge_type, edges in data['edges'].items():
        print(f"- {edge_type}: {len(edges)} edges")
    
    print("\n✅ ArangoDB Enhanced Renderer test completed!")