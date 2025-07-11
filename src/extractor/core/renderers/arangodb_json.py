"""
ArangoDB JSON renderer that produces database-ready JSON output for ArangoDB integration.
Module: arangodb_json.py

This renderer creates a JSON structure in the exact format required by ArangoDB integration,
with document hierarchical structure, metadata, validation information, and raw corpus text.

Output Format:
{
  "document": {
    "id": "unique_document_id",
    "pages": [
      {
        "blocks": [
          {
            "type": "section_header",
            "text": "Introduction to Topic",
            "level": 1
          },
          {
            "type": "text",
            "text": "This is the content text."
          }
        ]
      }
    ]
  },
  "metadata": {
    "title": "Document Title",
    "processing_time": 1.2
  },
  "validation": {
    "corpus_validation": {
      "performed": true,
      "threshold": 97,
      "raw_corpus_length": 5000
    }
  },
  "raw_corpus": {
    "full_text": "Complete document text content...",
    "pages": [
      {
        "page_num": 0,
        "text": "Page content...",
        "tables": []
      }
    ],
    "total_pages": 1
  }
}
"""
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel

from extractor.core.renderers import BaseRenderer
from extractor.core.schema import BlockTypes
from extractor.core.schema.blocks import Block
from extractor.core.schema.document import Document


class BlockOutputArangoDB(BaseModel):
    """Model for block output."""
    type: str  # Block type (section_header, text, code, table, etc.)
    text: str  # Text content of the block
    level: Optional[int] = None  # Level for section headers
    language: Optional[str] = None  # Language for code blocks
    csv: Optional[str] = None  # CSV data for tables
    json_data: Optional[Dict[str, Any]] = None  # JSON data for tables
    breadcrumbs: Optional[List[Dict[str, Any]]] = None  # Section breadcrumbs
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata (extraction details, quality metrics, etc.)


class PageOutput(BaseModel):
    """Model for page output."""
    blocks: List[BlockOutputArangoDB]


class DocumentOutput(BaseModel):
    """Model for document output."""
    id: str  # Unique document identifier
    pages: List[PageOutput]


class PageCorpus(BaseModel):
    """Model for page corpus text."""
    page_num: int
    text: str
    tables: List[Dict[str, Any]] = []


class RawCorpus(BaseModel):
    """Model for raw corpus text."""
    full_text: str  # Complete document text content
    pages: List[PageCorpus]  # Page-by-page text content
    total_pages: int  # Total number of pages


class CorpusValidation(BaseModel):
    """Model for corpus validation information."""
    performed: bool = False
    threshold: Optional[int] = None
    raw_corpus_length: Optional[int] = None


class ValidationInfo(BaseModel):
    """Model for validation information."""
    corpus_validation: CorpusValidation


class ArangoDBOutput(BaseModel):
    """Output model for ArangoDB integration."""
    document: DocumentOutput
    metadata: Dict[str, Any]
    validation: ValidationInfo
    raw_corpus: RawCorpus


class ArangoDBRenderer(BaseRenderer):
    """
    Renderer that produces ArangoDB-ready JSON output for ArangoDB integration.
    Creates document structure with blocks, metadata, validation, and raw corpus text.
    """
    
    def __call__(self, document: Document) -> ArangoDBOutput:
        """
        Convert document to ArangoDB-ready JSON format for integration.
        
        Args:
            document: The Document object to render
            
        Returns:
            ArangoDBOutput containing document structure, metadata, validation, and raw corpus
        """
        # Get document output
        document_output = document.render()
        
        # Extract document ID or generate one if not available
        doc_id = getattr(document, 'id', None) or f"{os.path.basename(document.filepath).split('.')[0]}_{uuid.uuid4().hex[:8]}"
        
        # Process pages and blocks
        pages = []
        raw_corpus_pages = []
        full_text_content = []
        
        # Extract start time if available for processing time calculation
        start_time = getattr(document, 'start_time', None)
        processing_time = None
        if start_time:
            processing_time = time.time() - start_time
        
        # Process each page
        for page in document.pages:
            # Extract blocks for this page
            page_blocks = self._extract_page_blocks(document, page)
            if page_blocks:
                pages.append(PageOutput(blocks=page_blocks))
            
            # Get page text for raw corpus
            page_text = self._extract_page_text(document, page)
            full_text_content.append(page_text)
            
            # Extract tables in this page
            page_tables = self._extract_page_tables(document, page)
            
            # Add to raw corpus pages
            raw_corpus_pages.append(PageCorpus(
                page_num=page.page_id,
                text=page_text,
                tables=page_tables
            ))
        
        # Combine all text for full corpus
        full_text = "\n\n".join(filter(None, full_text_content))
        
        # Check if corpus validation was performed
        corpus_validation = CorpusValidation(performed=False)
        if hasattr(document, 'metadata') and document.metadata:
            validation_info = document.metadata.get('validation', {})
            if validation_info:
                corpus_validation = CorpusValidation(
                    performed=True,
                    threshold=validation_info.get('threshold', 97),
                    raw_corpus_length=len(full_text)
                )
        
        # Create metadata with all required fields
        metadata = {
            "title": self._extract_document_title(document),
            "filepath": document.filepath,
            "page_count": len(document.pages),
            "author": None,
            "creation_date": None,
            "modification_date": None,
            "language": "en",  # Default, should be detected
            "subject": None,
            "keywords": [],
            "producer": None,
            "creator": None
        }
        
        if processing_time:
            metadata["processing_time"] = round(processing_time, 2)
        
        # Update with document metadata if available
        if hasattr(document, 'metadata') and document.metadata:
            for key, value in document.metadata.items():
                if key != 'validation' and value is not None:
                    metadata[key] = value
        
        return ArangoDBOutput(
            document=DocumentOutput(
                id=doc_id,
                pages=pages
            ),
            metadata=metadata,
            validation=ValidationInfo(
                corpus_validation=corpus_validation
            ),
            raw_corpus=RawCorpus(
                full_text=full_text,
                pages=raw_corpus_pages,
                total_pages=len(document.pages)
            )
        )
    
    def _extract_page_blocks(self, document: Document, page) -> List[BlockOutputArangoDB]:
        """
        Extract blocks from a page in the required format.
        
        Args:
            document: Document object
            page: Page object to extract blocks from
            
        Returns:
            List of BlockOutput objects
        """
        blocks = []
        
        # Get all blocks for this page
        page_blocks = [block for block in document.contained_blocks() if block.page_id == page.page_id]
        
        # Sort blocks by vertical position
        page_blocks.sort(key=lambda b: b.polygon.bbox[1] if b.polygon else 0)
        
        for block in page_blocks:
            block_type = str(block.block_type).split('.')[-1].lower()
            
            # Skip low-level blocks
            if block_type in ['line', 'span']:
                continue
            
            # Transform block type names to match required format
            if block_type == 'sectionheader':
                block_type = 'section_header'
            elif block_type == 'basetable':
                block_type = 'table'
            elif block_type == 'picture':
                block_type = 'image'
            
            # Get text content
            text = block.raw_text(document).strip()
            if not text:
                continue
            
            # Get breadcrumbs for this block
            breadcrumbs = self._extract_breadcrumbs_for_block(document, block)
            
            # Create block output based on type
            if block_type == 'section_header':
                level = getattr(block, 'heading_level', 1) if hasattr(block, 'heading_level') else 1
                block_output = BlockOutputArangoDB(
                    type=block_type,
                    text=text,
                    level=level
                )
                # Add breadcrumbs if available
                if breadcrumbs:
                    block_output.breadcrumbs = breadcrumbs
                blocks.append(block_output)
            elif block_type == 'code':
                language = getattr(block, 'language', '') if hasattr(block, 'language') else ''
                block_output = BlockOutputArangoDB(
                    type=block_type,
                    text=text,
                    language=language
                )
                if breadcrumbs:
                    block_output.breadcrumbs = breadcrumbs
                blocks.append(block_output)
            elif block_type == 'table':
                # Get CSV and JSON representations if available
                csv_data = None
                json_data = None
                if hasattr(block, "generate_csv"):
                    csv_data = block.generate_csv(document, [])
                if hasattr(block, "generate_json"):
                    json_str = block.generate_json(document, [])
                    # Parse JSON string to dict
                    try:
                        json_data = json.loads(json_str)
                    except (json.JSONDecodeError, TypeError):
                        json_data = None
                
                # Create base block output
                block_output = BlockOutputArangoDB(
                    type=block_type,
                    text=text,
                    csv=csv_data,
                    json_data=json_data
                )
                
                # Collect metadata for tables
                metadata = {}
                if hasattr(block, 'extraction_method') and block.extraction_method:
                    metadata['extraction_method'] = block.extraction_method
                    
                if hasattr(block, 'extraction_details') and block.extraction_details:
                    metadata['extraction_details'] = block.extraction_details
                
                if hasattr(block, 'quality_score') and block.quality_score is not None:
                    metadata['quality_score'] = block.quality_score
                    
                if hasattr(block, 'quality_metrics') and block.quality_metrics:
                    metadata['quality_metrics'] = block.quality_metrics
                
                if hasattr(block, 'merge_info') and block.merge_info:
                    metadata['merge_info'] = block.merge_info
                
                # Set metadata if any was collected
                if metadata:
                    block_output.metadata = metadata
                
                if breadcrumbs:
                    block_output.breadcrumbs = breadcrumbs
                blocks.append(block_output)
            else:
                block_output = BlockOutputArangoDB(
                    type=block_type,
                    text=text
                )
                if breadcrumbs:
                    block_output.breadcrumbs = breadcrumbs
                blocks.append(block_output)
        
        return blocks
    
    
    def _extract_breadcrumbs_for_block(self, document: Document, block) -> Optional[List[Dict[str, Any]]]:
        """
        Extract breadcrumbs for a block based on its section context.
        
        Args:
            document: Document object
            block: Block to get breadcrumbs for
            
        Returns:
            List of breadcrumb dictionaries or None
        """
        # Get the section hierarchy
        hierarchy = document.get_section_hierarchy()
        
        # Find which section this block belongs to
        current_section = None
        current_level = None
        
        # Check all sections to find where this block belongs
        for level_str, sections in hierarchy.items():
            level = int(level_str)
            for section in sections:
                # Check if block is after this section header
                if hasattr(block, 'page_id') and hasattr(section, 'page_id'):
                    if block.page_id == section['page_id']:
                        # Simple check: if block comes after section header
                        if hasattr(block, 'polygon') and block.polygon:
                            block_y = block.polygon.bbox[1]
                            section_y = section.get('bbox', [0, 0, 0, 0])[1]
                            if block_y >= section_y:
                                if current_section is None or section_y > current_section.get('bbox', [0, 0, 0, 0])[1]:
                                    current_section = section
                                    current_level = level
        
        if not current_section:
            return None
            
        # Build breadcrumb path
        breadcrumbs = []
        
        # Add the current section
        breadcrumbs.append({
            "level": current_level,
            "title": current_section.get('title', ''),
            "hash": current_section.get('hash', '')
        })
        
        # Add parent sections (simplified - would need proper parent tracking)
        # For now, just return the current section
        
        return breadcrumbs

    
    def _extract_page_text(self, document: Document, page) -> str:
        """
        Extract all text content from a page.
        
        Args:
            document: Document object
            page: Page object to extract text from
            
        Returns:
            Combined text content of the page
        """
        # Get all text blocks for this page
        page_blocks = [block for block in document.contained_blocks() if block.page_id == page.page_id]
        
        # Sort blocks by vertical position
        page_blocks.sort(key=lambda b: b.polygon.bbox[1] if b.polygon else 0)
        
        # Extract text from each block
        text_content = []
        for block in page_blocks:
            text = block.raw_text(document).strip()
            if text:
                text_content.append(text)
        
        return "\n\n".join(text_content)
    
    def _extract_page_tables(self, document: Document, page) -> List[Dict[str, Any]]:
        """
        Extract tables from a page.
        
        Args:
            document: Document object
            page: Page object to extract tables from
            
        Returns:
            List of table data
        """
        tables = []
        
        # Get all table blocks for this page
        table_blocks = [block for block in document.contained_blocks([BlockTypes.Table]) 
                        if block.page_id == page.page_id]
        
        for table_block in table_blocks:
            table_data = {
                "text": table_block.raw_text(document).strip()
            }
            
            # Add CSV and JSON representations if available
            if hasattr(table_block, "generate_csv"):
                table_data["csv"] = table_block.generate_csv(document, [])
            if hasattr(table_block, "generate_json"):
                table_data["json"] = table_block.generate_json(document, [])
            
            tables.append(table_data)
        
        return tables
    
    def _extract_document_title(self, document: Document) -> str:
        """
        Extract the document title.
        
        Args:
            document: Document object
            
        Returns:
            Document title or filename if no title found
        """
        # First check if there's a title in metadata
        if hasattr(document, 'metadata') and document.metadata and 'title' in document.metadata:
            return document.metadata['title']
        
        # Try to find the first H1 header
        section_blocks = document.contained_blocks([BlockTypes.SectionHeader])
        for block in section_blocks:
            if hasattr(block, 'heading_level') and block.heading_level == 1:
                return block.raw_text(document).strip()
        
        # If no title found, use the filename
        return os.path.basename(document.filepath).split('.')[0]
    
    def to_json(self, output: ArangoDBOutput) -> str:
        """
        Convert the output model to a JSON string.
        
        Args:
            output: ArangoDBOutput model
            
        Returns:
            JSON string representation
        """
        return json.dumps(output.model_dump(), indent=2)
    
    # Keep _extract_document_metadata for compatibility but it's not used in the new implementation
    def _extract_document_metadata(self, document: Document, document_output: BlockOutputArangoDB) -> Dict[str, Any]:
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
