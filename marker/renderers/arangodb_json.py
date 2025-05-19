"""
ArangoDB JSON renderer that produces flattened, database-ready JSON output.

This renderer creates a flattened list of objects, each containing its full section
context, designed for easy insertion into ArangoDB or similar document databases.
"""
import json
import uuid
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel

from marker.renderers import BaseRenderer
from marker.schema import BlockTypes
from marker.schema.blocks import Block, BlockOutput
from marker.schema.document import Document


class ArangoDBObject(BaseModel):
    """Base model for ArangoDB objects."""
    _key: str  # Unique identifier for ArangoDB (_key)
    _type: str  # Type of object (section, text, table, image, etc.)
    content: Any  # Main content
    text: Optional[str] = None  # Plain text content when available
    page_id: Optional[int] = None  # Page number
    position: Optional[Dict[str, float]] = None  # Position data
    
    # Section context
    section_id: Optional[str] = None  # ID of the containing section
    section_hash: Optional[str] = None  # Hash of the containing section
    section_title: Optional[str] = None  # Title of the containing section
    section_level: Optional[int] = None  # Level of the containing section (h1=1, h2=2, etc.)
    section_path: Optional[List[Dict[str, Any]]] = None  # Full breadcrumb path
    section_path_titles: Optional[List[str]] = None  # List of section titles in path
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata


class ArangoDBOutput(BaseModel):
    """Output model for ArangoDB export."""
    objects: List[ArangoDBObject]
    document_metadata: Dict[str, Any]


class ArangoDBRenderer(BaseRenderer):
    """
    Renderer that produces flattened, ArangoDB-ready JSON output.
    Each object contains its own section context for easy querying.
    """
    
    def __call__(self, document: Document) -> ArangoDBOutput:
        """
        Convert document to ArangoDB-ready JSON format.
        
        Args:
            document: The Document object to render
            
        Returns:
            ArangoDBOutput containing a flattened list of objects
        """
        # Get document output and section hierarchy
        document_output = document.render()
        section_hierarchy = document.get_section_hierarchy()
        section_breadcrumbs = document.get_section_breadcrumbs()
        
        # Create flattened objects list
        objects = []
        
        # Process the document structure
        self._process_document_structure(
            document, 
            document_output, 
            objects, 
            section_hierarchy, 
            section_breadcrumbs
        )
        
        # Add document metadata
        document_metadata = self._extract_document_metadata(document, document_output)
        
        return ArangoDBOutput(
            objects=objects,
            document_metadata=document_metadata
        )
    
    def _process_document_structure(
        self, 
        document: Document, 
        output: BlockOutput, 
        objects: List[ArangoDBObject],
        section_hierarchy: Dict[str, Any],
        section_breadcrumbs: Dict[str, Any],
        current_section_context: Optional[Dict[str, Any]] = None
    ):
        """
        Process document structure recursively, building flattened objects.
        
        Args:
            document: Document object
            output: BlockOutput to process
            objects: List of objects to append to
            section_hierarchy: Document section hierarchy
            section_breadcrumbs: Document section breadcrumbs
            current_section_context: Current section context information
        """
        # Handle different block types
        if output.id.block_type == BlockTypes.SectionHeader:
            # Create a new section context
            block = document.get_block(output.id)
            if block and hasattr(block, 'heading_level') and block.heading_level:
                section_hash = getattr(block, 'section_hash', str(uuid.uuid4()))
                section_context = {
                    "id": str(output.id),
                    "hash": section_hash,
                    "title": block.raw_text(document).strip(),
                    "level": block.heading_level,
                    "path": section_breadcrumbs.get(section_hash, [])
                }
                
                # Create section object
                section_object = self._create_section_object(block, document, section_context)
                objects.append(section_object)
                
                # Update current context for child blocks
                current_section_context = section_context
        
        elif current_section_context:
            # Create content object with section context
            content_object = self._create_content_object(output, document, current_section_context)
            if content_object:
                objects.append(content_object)
        
        # Process children recursively
        if output.children:
            for child in output.children:
                self._process_document_structure(
                    document,
                    child,
                    objects,
                    section_hierarchy,
                    section_breadcrumbs,
                    current_section_context
                )
    
    def _create_section_object(self, block: Block, document: Document, section_context: Dict[str, Any]) -> ArangoDBObject:
        """
        Create an ArangoDBObject for a section header.
        
        Args:
            block: SectionHeader block
            document: Document object
            section_context: Section context information
            
        Returns:
            ArangoDBObject for the section
        """
        # Extract section path titles
        section_path_titles = []
        for item in section_context.get("path", []):
            if "title" in item:
                section_path_titles.append(item["title"])
        
        # Create section object
        return ArangoDBObject(
            _key=f"section_{section_context['hash']}",
            _type="section",
            content={
                "title": section_context["title"],
                "level": section_context["level"],
                "hash": section_context["hash"]
            },
            text=section_context["title"],
            page_id=block.page_id,
            position={
                "left": block.polygon.bbox[0] if block.polygon else 0,
                "top": block.polygon.bbox[1] if block.polygon else 0,
                "right": block.polygon.bbox[2] if block.polygon else 0,
                "bottom": block.polygon.bbox[3] if block.polygon else 0
            },
            section_id=section_context["id"],
            section_hash=section_context["hash"],
            section_title=section_context["title"],
            section_level=section_context["level"],
            section_path=section_context["path"],
            section_path_titles=section_path_titles,
            metadata={
                "block_id": str(block.id)
            }
        )
    
    def _create_content_object(self, output: BlockOutput, document: Document, section_context: Dict[str, Any]) -> Optional[ArangoDBObject]:
        """
        Create an ArangoDBObject for a content block.
        
        Args:
            output: BlockOutput of the content
            document: Document object
            section_context: Current section context
            
        Returns:
            ArangoDBObject for the content or None if not a supported content type
        """
        block = document.get_block(output.id)
        if not block:
            return None
            
        # Extract section path titles
        section_path_titles = []
        for item in section_context.get("path", []):
            if "title" in item:
                section_path_titles.append(item["title"])
        
        # Handle different content types
        if output.id.block_type == BlockTypes.Text:
            return self._create_text_object(block, document, section_context, section_path_titles)
            
        elif output.id.block_type in (BlockTypes.Table, BlockTypes.BaseTable):
            return self._create_table_object(block, document, section_context, section_path_titles)
            
        elif output.id.block_type in (BlockTypes.Picture, BlockTypes.Figure):
            return self._create_image_object(block, document, section_context, section_path_titles)
            
        elif output.id.block_type == BlockTypes.Code:
            return self._create_code_object(block, document, section_context, section_path_titles)
            
        elif output.id.block_type == BlockTypes.Equation:
            return self._create_equation_object(block, document, section_context, section_path_titles)

        return None
    
    def _create_text_object(self, block: Block, document: Document, section_context: Dict[str, Any], section_path_titles: List[str]) -> ArangoDBObject:
        """Create an object for text content."""
        text = block.raw_text(document)
        return ArangoDBObject(
            _key=f"text_{block.page_id}_{block.block_id}",
            _type="text",
            content=text,
            text=text,
            page_id=block.page_id,
            position={
                "left": block.polygon.bbox[0] if block.polygon else 0,
                "top": block.polygon.bbox[1] if block.polygon else 0,
                "right": block.polygon.bbox[2] if block.polygon else 0,
                "bottom": block.polygon.bbox[3] if block.polygon else 0
            },
            section_id=section_context["id"],
            section_hash=section_context["hash"],
            section_title=section_context["title"],
            section_level=section_context["level"],
            section_path=section_context["path"],
            section_path_titles=section_path_titles,
            metadata={
                "block_id": str(block.id)
            }
        )
    
    def _create_table_object(self, block: Block, document: Document, section_context: Dict[str, Any], section_path_titles: List[str]) -> ArangoDBObject:
        """Create an object for table content."""
        # Get CSV and JSON representations if available
        csv_data = None
        json_data = None
        if hasattr(block, "generate_csv"):
            csv_data = block.generate_csv(document, [])
        if hasattr(block, "generate_json"):
            json_data = block.generate_json(document, [])
            
        # Get raw text
        text = block.raw_text(document)
        
        return ArangoDBObject(
            _key=f"table_{block.page_id}_{block.block_id}",
            _type="table",
            content={
                "csv": csv_data,
                "json": json_data,
                "text": text
            },
            text=text,
            page_id=block.page_id,
            position={
                "left": block.polygon.bbox[0] if block.polygon else 0,
                "top": block.polygon.bbox[1] if block.polygon else 0,
                "right": block.polygon.bbox[2] if block.polygon else 0,
                "bottom": block.polygon.bbox[3] if block.polygon else 0
            },
            section_id=section_context["id"],
            section_hash=section_context["hash"],
            section_title=section_context["title"],
            section_level=section_context["level"],
            section_path=section_context["path"],
            section_path_titles=section_path_titles,
            metadata={
                "block_id": str(block.id)
            }
        )
    
    def _create_image_object(self, block: Block, document: Document, section_context: Dict[str, Any], section_path_titles: List[str]) -> ArangoDBObject:
        """Create an object for image content."""
        # Get caption and description if available
        caption = getattr(block, "caption", "")
        description = getattr(block, "description", "")
        
        # Check metadata for generated description
        if hasattr(block, "metadata") and block.metadata and "generated_description" in block.metadata:
            description = block.metadata["generated_description"]
            
        # Combine caption and description for text
        text = caption
        if description and description != caption:
            text = f"{caption}\n\n{description}" if caption else description
            
        return ArangoDBObject(
            _key=f"image_{block.page_id}_{block.block_id}",
            _type="image",
            content={
                "caption": caption,
                "description": description
            },
            text=text,
            page_id=block.page_id,
            position={
                "left": block.polygon.bbox[0] if block.polygon else 0,
                "top": block.polygon.bbox[1] if block.polygon else 0,
                "right": block.polygon.bbox[2] if block.polygon else 0,
                "bottom": block.polygon.bbox[3] if block.polygon else 0
            },
            section_id=section_context["id"],
            section_hash=section_context["hash"],
            section_title=section_context["title"],
            section_level=section_context["level"],
            section_path=section_context["path"],
            section_path_titles=section_path_titles,
            metadata={
                "block_id": str(block.id)
            }
        )
    
    def _create_code_object(self, block: Block, document: Document, section_context: Dict[str, Any], section_path_titles: List[str]) -> ArangoDBObject:
        """Create an object for code content."""
        # Get language if available
        language = getattr(block, "language", "")
        
        # Get text content
        text = block.raw_text(document)
        
        return ArangoDBObject(
            _key=f"code_{block.page_id}_{block.block_id}",
            _type="code",
            content={
                "code": text,
                "language": language
            },
            text=text,
            page_id=block.page_id,
            position={
                "left": block.polygon.bbox[0] if block.polygon else 0,
                "top": block.polygon.bbox[1] if block.polygon else 0,
                "right": block.polygon.bbox[2] if block.polygon else 0,
                "bottom": block.polygon.bbox[3] if block.polygon else 0
            },
            section_id=section_context["id"],
            section_hash=section_context["hash"],
            section_title=section_context["title"],
            section_level=section_context["level"],
            section_path=section_context["path"],
            section_path_titles=section_path_titles,
            metadata={
                "block_id": str(block.id)
            }
        )
    
    def _create_equation_object(self, block: Block, document: Document, section_context: Dict[str, Any], section_path_titles: List[str]) -> ArangoDBObject:
        """Create an object for equation content."""
        # Get equation content
        text = block.raw_text(document)
        latex = getattr(block, "latex", text)
        
        return ArangoDBObject(
            _key=f"equation_{block.page_id}_{block.block_id}",
            _type="equation",
            content={
                "text": text,
                "latex": latex
            },
            text=text,
            page_id=block.page_id,
            position={
                "left": block.polygon.bbox[0] if block.polygon else 0,
                "top": block.polygon.bbox[1] if block.polygon else 0,
                "right": block.polygon.bbox[2] if block.polygon else 0,
                "bottom": block.polygon.bbox[3] if block.polygon else 0
            },
            section_id=section_context["id"],
            section_hash=section_context["hash"],
            section_title=section_context["title"],
            section_level=section_context["level"],
            section_path=section_context["path"],
            section_path_titles=section_path_titles,
            metadata={
                "block_id": str(block.id)
            }
        )
    
    def _extract_document_metadata(self, document: Document, document_output: BlockOutput) -> Dict[str, Any]:
        """Extract metadata about the document."""
        # Count blocks by type
        block_counts = {}
        all_blocks = document.contained_blocks()
        for block in all_blocks:
            block_type = str(block.block_type)
            if block_type not in block_counts:
                block_counts[block_type] = 0
            block_counts[block_type] += 1
        
        # Get section information
        sections_by_level = {}
        section_blocks = document.contained_blocks([BlockTypes.SectionHeader])
        for section in section_blocks:
            if hasattr(section, 'heading_level') and section.heading_level:
                level = section.heading_level
                if level not in sections_by_level:
                    sections_by_level[level] = 0
                sections_by_level[level] += 1
        
        return {
            "filepath": document.filepath,
            "page_count": len(document.pages),
            "block_counts": block_counts,
            "section_counts": sections_by_level
        }