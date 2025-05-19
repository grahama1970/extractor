"""
Search and debug functionality for Marker document models.
"""

import json
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from pydantic import BaseModel

from marker.schema.document import Document
from marker.schema.blocks.base import BlockOutput


class SearchResult(BaseModel):
    """A single search result."""
    id: str
    block_type: str
    path: List[str]  # Path from root to this block
    content: Optional[str] = None
    html: Optional[str] = None
    bbox: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None
    children_count: int = 0
    match_reason: str = ""


class SearchCriteria(BaseModel):
    """Criteria for searching within a document model."""
    text: Optional[str] = None  # Text to search for (case-insensitive)
    block_type: Optional[str] = None  # Block type to filter by
    section_id: Optional[str] = None  # Specific section ID to search within
    has_images: Optional[bool] = None  # Filter blocks that contain images
    min_children: Optional[int] = None  # Minimum number of children
    max_children: Optional[int] = None  # Maximum number of children
    bbox_contains: Optional[List[float]] = None  # Point that bbox should contain
    metadata_key: Optional[str] = None  # Key that should exist in metadata
    metadata_value: Optional[Any] = None  # Value to match in metadata
    max_results: int = 100  # Maximum number of results to return


class DocumentSearcher:
    """Search and debug functionality for document models."""
    
    def __init__(self, document: Document):
        self.document = document
    
    def search(self, criteria: SearchCriteria) -> List[SearchResult]:
        """Search the document based on given criteria."""
        results = []
        self._search_recursive(self.document, criteria, results, [])
        return results[:criteria.max_results]
    
    def _search_recursive(
        self, 
        node: Union[Document, BlockOutput], 
        criteria: SearchCriteria, 
        results: List[SearchResult],
        path: List[str]
    ):
        """Recursively search through the document structure."""
        # Check if current node matches criteria
        match_reasons = []
        
        # Extract node properties
        node_id = getattr(node, 'id', str(type(node).__name__))
        node_type = getattr(node, 'block_type', type(node).__name__)
        node_html = getattr(node, 'html', None)
        node_bbox = None
        
        # Handle bbox which might be a list or a property
        if hasattr(node, 'bbox'):
            if isinstance(node.bbox, list):
                node_bbox = node.bbox
            else:
                node_bbox = getattr(node.bbox, 'bbox', None)
        elif hasattr(node, 'polygon') and node.polygon:
            # Handle polygon which might have bbox property
            if hasattr(node.polygon, 'bbox'):
                node_bbox = node.polygon.bbox
        
        # Check text match
        if criteria.text and node_html:
            if criteria.text.lower() in node_html.lower():
                match_reasons.append(f"text contains '{criteria.text}'")
        
        # Check block type
        if criteria.block_type:
            if node_type == criteria.block_type:
                match_reasons.append(f"block type is '{criteria.block_type}'")
            else:
                # Skip this node if block type doesn't match
                if not hasattr(node, 'children'):
                    return
        
        # Check section ID
        if criteria.section_id:
            if str(node_id) == criteria.section_id:
                match_reasons.append(f"section ID matches '{criteria.section_id}'")
        
        # Check images
        if criteria.has_images is not None:
            has_images = hasattr(node, 'images') and bool(node.images)
            if has_images == criteria.has_images:
                match_reasons.append(f"has images: {criteria.has_images}")
        
        # Check children count
        children_count = 0
        if hasattr(node, 'children') and node.children:
            children_count = len(node.children)
        
        if criteria.min_children is not None:
            if children_count >= criteria.min_children:
                match_reasons.append(f"has at least {criteria.min_children} children")
        
        if criteria.max_children is not None:
            if children_count <= criteria.max_children:
                match_reasons.append(f"has at most {criteria.max_children} children")
        
        # Check bbox contains point
        if criteria.bbox_contains and node_bbox:
            x, y = criteria.bbox_contains
            if (node_bbox[0] <= x <= node_bbox[2] and 
                node_bbox[1] <= y <= node_bbox[3]):
                match_reasons.append(f"bbox contains point ({x}, {y})")
        
        # Check metadata
        node_metadata = {}
        if hasattr(node, 'metadata'):
            node_metadata = node.metadata
        elif hasattr(node, '__dict__'):
            # Extract custom attributes as metadata
            for key, value in node.__dict__.items():
                if not key.startswith('_') and key not in ['id', 'children', 'html', 'polygon']:
                    node_metadata[key] = value
        
        if criteria.metadata_key:
            if criteria.metadata_key in node_metadata:
                match_reasons.append(f"has metadata key '{criteria.metadata_key}'")
                
                if criteria.metadata_value is not None:
                    if node_metadata[criteria.metadata_key] == criteria.metadata_value:
                        match_reasons.append(
                            f"metadata[{criteria.metadata_key}] = {criteria.metadata_value}"
                        )
        
        # Add to results if any criteria matched
        if match_reasons:
            result = SearchResult(
                id=str(node_id),
                block_type=node_type,
                path=path + [str(node_id)],
                content=node_html[:200] + "..." if node_html and len(node_html) > 200 else node_html,
                html=node_html,
                bbox=node_bbox,
                metadata=node_metadata,
                children_count=children_count,
                match_reason="; ".join(match_reasons)
            )
            results.append(result)
        
        # Recursively search children
        if hasattr(node, 'children') and node.children:
            for child in node.children:
                self._search_recursive(
                    child, 
                    criteria, 
                    results, 
                    path + [str(node_id)]
                )
    
    def get_node_by_id(self, node_id: str) -> Optional[Dict]:
        """Get a specific node by its ID and return its full structure."""
        result = self._find_node_by_id(self.document, node_id)
        if result:
            return self._node_to_dict(result)
        return None
    
    def _find_node_by_id(
        self, 
        node: Union[Document, BlockOutput], 
        target_id: str
    ) -> Optional[Union[Document, BlockOutput]]:
        """Find a node by ID recursively."""
        if hasattr(node, 'id') and str(node.id) == target_id:
            return node
        
        if hasattr(node, 'children') and node.children:
            for child in node.children:
                result = self._find_node_by_id(child, target_id)
                if result:
                    return result
        
        return None
    
    def _node_to_dict(self, node: Union[Document, BlockOutput]) -> Dict:
        """Convert a node to a dictionary representation."""
        result = {}
        
        # Basic properties
        if hasattr(node, 'id'):
            result['id'] = str(node.id)
        
        if hasattr(node, 'block_type'):
            result['block_type'] = node.block_type
        else:
            result['block_type'] = type(node).__name__
        
        # Content
        if hasattr(node, 'html'):
            result['html'] = node.html
        
        # Bounding box
        if hasattr(node, 'bbox'):
            if isinstance(node.bbox, list):
                result['bbox'] = node.bbox
            else:
                result['bbox'] = getattr(node.bbox, 'bbox', None)
        elif hasattr(node, 'polygon') and node.polygon:
            # Handle polygon which might have bbox property
            if hasattr(node.polygon, 'bbox'):
                result['bbox'] = node.polygon.bbox
            if hasattr(node.polygon, 'polygon'):
                result['polygon'] = node.polygon.polygon
        
        # Images
        if hasattr(node, 'images') and node.images:
            result['images'] = node.images
        
        # Metadata and other attributes
        metadata = {}
        if hasattr(node, 'metadata'):
            metadata = node.metadata
        elif hasattr(node, '__dict__'):
            for key, value in node.__dict__.items():
                if not key.startswith('_') and key not in ['id', 'children', 'html', 'polygon', 'images']:
                    metadata[key] = value
        
        if metadata:
            result['metadata'] = metadata
        
        # Children (simplified)
        if hasattr(node, 'children') and node.children:
            result['children'] = []
            for child in node.children:
                child_summary = {
                    'id': str(getattr(child, 'id', 'unknown')),
                    'block_type': getattr(child, 'block_type', type(child).__name__),
                }
                if hasattr(child, 'html') and child.html:
                    child_summary['preview'] = child.html[:50] + "..." if len(child.html) > 50 else child.html
                result['children'].append(child_summary)
        
        return result
    
    def get_structure_summary(self) -> Dict:
        """Get a summary of the document structure."""
        summary = {
            'total_blocks': 0,
            'block_types': {},
            'max_depth': 0,
            'sections': [],
            'pages': [],
            'images_count': 0,
            'tables_count': 0
        }
        
        self._analyze_structure(self.document, summary, 0)
        
        return summary
    
    def _analyze_structure(self, node: Union[Document, BlockOutput], summary: Dict, depth: int):
        """Analyze document structure recursively."""
        summary['total_blocks'] += 1
        summary['max_depth'] = max(summary['max_depth'], depth)
        
        # Count block types
        node_type = getattr(node, 'block_type', type(node).__name__)
        if node_type not in summary['block_types']:
            summary['block_types'][node_type] = 0
        summary['block_types'][node_type] += 1
        
        # Track special elements
        if node_type == 'Section':
            section_info = {
                'id': str(getattr(node, 'id', 'unknown')),
                'children_count': len(node.children) if hasattr(node, 'children') else 0
            }
            if hasattr(node, 'metadata') and 'title' in node.metadata:
                section_info['title'] = node.metadata['title']
            summary['sections'].append(section_info)
        
        elif node_type == 'Page':
            page_info = {
                'id': str(getattr(node, 'id', 'unknown')),
                'children_count': len(node.children) if hasattr(node, 'children') else 0
            }
            summary['pages'].append(page_info)
        
        elif node_type in ['Image', 'Figure', 'Picture']:
            summary['images_count'] += 1
        
        elif node_type == 'Table':
            summary['tables_count'] += 1
        
        # Recurse into children
        if hasattr(node, 'children') and node.children:
            for child in node.children:
                self._analyze_structure(child, summary, depth + 1)


def search_document(
    document_path: Path,
    text: Optional[str] = None,
    block_type: Optional[str] = None,
    section_id: Optional[str] = None,
    has_images: Optional[bool] = None,
    format_output: bool = True
) -> Union[List[SearchResult], str]:
    """
    Search a document for specific content or structure.
    
    Args:
        document_path: Path to the JSON document
        text: Text to search for
        block_type: Block type to filter by
        section_id: Specific section ID
        has_images: Filter by presence of images
        format_output: Whether to format output as JSON string
    
    Returns:
        List of search results or formatted JSON string
    """
    # Load document
    with open(document_path, 'r') as f:
        doc_data = json.load(f)
    
    # Create document model (simplified - normally would use proper deserialization)
    from types import SimpleNamespace
    doc = json.loads(json.dumps(doc_data), object_hook=lambda d: SimpleNamespace(**d))
    
    # Create searcher
    searcher = DocumentSearcher(doc)
    
    # Build criteria
    criteria = SearchCriteria(
        text=text,
        block_type=block_type,
        section_id=section_id,
        has_images=has_images
    )
    
    # Search
    results = searcher.search(criteria)
    
    if format_output:
        return json.dumps([r.model_dump() for r in results], indent=2)
    return results