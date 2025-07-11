"""
Module: enhanced_document.py
Description: Enhanced hierarchical document model for Marker
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field
from extractor.core.schema import BlockTypes
from extractor.core.schema.blocks import Block
from extractor.core.schema.blocks.sectionheader import SectionHeader
from extractor.core.schema.polygon import PolygonBox
import hashlib


class FileMetadata(BaseModel):
    """File-level metadata"""
    filepath: Path
    file_size: int  # bytes
    file_hash: str  # SHA-256
    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None
    mime_type: str = "application/pdf"

class ProcessingMetadata(BaseModel):
    """Processing/extraction metadata"""
    extraction_date: datetime = Field(default_factory=datetime.now)
    extraction_duration: float = 0.0  # seconds
    processor_version: str = "1.0.0"
    ocr_engine: Optional[str] = None
    quality_metrics: Dict[str, float] = {}
    errors_encountered: List[str] = []
    processing_config: Dict[str, Any] = {}

class DocumentMetadata(BaseModel):
    """Document content metadata"""
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    keywords: List[str] = []
    language: str = "en"
    page_count: int = 0
    document_summary: Optional[str] = None
    
    # Content statistics
    total_sections: int = 0
    total_words: int = 0
    total_images: int = 0
    total_tables: int = 0
    estimated_reading_time: int = 0  # minutes

class SectionMetadata(BaseModel):
    """Section-specific metadata"""
    summary: Optional[str] = None
    key_points: List[str] = []
    word_count: int = 0
    reading_time: int = 0
    depth_level: int = 0
    section_number: str = ""  # e.g., "1.2.3"
    
    # Section hierarchy (breadcrumb)
    hierarchy_titles: List[str] = []  # ["Introduction", "Background", "Prior Work"]
    hierarchy_hashes: List[str] = []  # Corresponding hashes for each level
    
    # Content analysis
    has_images: bool = False
    has_tables: bool = False
    has_equations: bool = False
    has_code: bool = False
    
    # Content type counts
    text_block_count: int = 0
    image_count: int = 0
    table_count: int = 0
    
    # Relationships
    parent_section_id: Optional[str] = None
    subsection_ids: List[str] = []

class Section(BaseModel):
    """A section with its content and subsections, preserving block order"""
    id: str
    header: SectionHeader
    metadata: SectionMetadata
    
    # Content blocks in original order (text, tables, images, etc.)
    content_blocks: List[Block] = []
    
    # Nested subsections
    subsections: List[Section] = []
    
    # Section hash (content-based)
    section_hash: str = ""
    
    def compute_section_hash(self) -> str:
        """Compute hash of section content including subsections"""
        content = self.header.html or ""
        for block in self.content_blocks:
            if hasattr(block, 'html') and block.html:
                content += block.html
            elif hasattr(block, 'text') and block.text:
                content += block.text
        for subsection in self.subsections:
            content += subsection.compute_section_hash()
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    def get_ordered_content(self, include_subsections: bool = False) -> List[Block]:
        """Get content blocks in their original order"""
        blocks = list(self.content_blocks)
        if include_subsections:
            for subsection in self.subsections:
                blocks.append(subsection.header)  # Include subsection header
                blocks.extend(subsection.get_ordered_content(include_subsections=True))
        return blocks
    
    def get_hierarchy_info(self) -> tuple[List[str], List[str]]:
        """Get the hierarchy titles and hashes for this section"""
        return self.metadata.hierarchy_titles, self.metadata.hierarchy_hashes
    
    def add_content_block(self, block: Block):
        """Add a content block while maintaining order"""
        self.content_blocks.append(block)
        
        # Update metadata
        if block.block_type == BlockTypes.Text:
            self.metadata.text_block_count += 1
        elif block.block_type in [BlockTypes.Picture, BlockTypes.Figure]:
            self.metadata.image_count += 1
            self.metadata.has_images = True
        elif block.block_type == BlockTypes.Table:
            self.metadata.table_count += 1
            self.metadata.has_tables = True
        elif block.block_type in [BlockTypes.Equation, BlockTypes.TextInlineMath]:
            self.metadata.has_equations = True
        elif block.block_type == BlockTypes.Code:
            self.metadata.has_code = True
    
    def find_subsection(self, section_number: str) -> Optional[Section]:
        """Find a subsection by its number (e.g., '1.2.3')"""
        for subsection in self.subsections:
            if subsection.metadata.section_number == section_number:
                return subsection
            # Recursive search
            found = subsection.find_subsection(section_number)
            if found:
                return found
        return None

class HierarchicalDocument(BaseModel):
    """Complete document with all metadata and hierarchical sections"""
    # File information
    file_metadata: FileMetadata
    
    # Processing information
    processing_metadata: ProcessingMetadata
    
    # Document information
    document_metadata: DocumentMetadata
    
    # Content (hierarchical sections)
    sections: List[Section] = []
    
    # Table of contents (generated from sections)
    table_of_contents: List[Dict[str, Any]] = []
    
    def add_section(self, section: Section, parent_section: Optional[Section] = None):
        """Add a section to the document hierarchy"""
        if parent_section is None:
            # Top-level section
            self.sections.append(section)
            section.metadata.depth_level = 0
            section.metadata.section_number = str(len(self.sections))
            section.metadata.hierarchy_titles = [section.header.html or ""]
            section.metadata.hierarchy_hashes = [section.compute_section_hash()]
        else:
            # Subsection
            parent_section.subsections.append(section)
            section.metadata.parent_section_id = parent_section.id
            section.metadata.depth_level = parent_section.metadata.depth_level + 1
            section.metadata.section_number = f"{parent_section.metadata.section_number}.{len(parent_section.subsections)}"
            
            # Build hierarchy info
            section.metadata.hierarchy_titles = parent_section.metadata.hierarchy_titles + [section.header.html or ""]
            section.metadata.hierarchy_hashes = parent_section.metadata.hierarchy_hashes + [section.compute_section_hash()]
        
        # Update document metadata
        self.document_metadata.total_sections += 1
    
    def get_section(self, section_id: str) -> Optional[Section]:
        """Get any section by ID, regardless of nesting"""
        for section in self.sections:
            if section.id == section_id:
                return section
            # Recursive search in subsections
            found = self._find_section_recursive(section, section_id)
            if found:
                return found
        return None
    
    def _find_section_recursive(self, section: Section, section_id: str) -> Optional[Section]:
        """Recursively find a section by ID"""
        for subsection in section.subsections:
            if subsection.id == section_id:
                return subsection
            found = self._find_section_recursive(subsection, section_id)
            if found:
                return found
        return None
    
    def get_section_by_number(self, section_number: str) -> Optional[Section]:
        """Get section by number like '1.2.3'"""
        parts = section_number.split('.')
        current_sections = self.sections
        current_section = None
        
        for i, part in enumerate(parts):
            try:
                idx = int(part) - 1
                if 0 <= idx < len(current_sections):
                    current_section = current_sections[idx]
                    if i < len(parts) - 1:
                        current_sections = current_section.subsections
                else:
                    return None
            except (ValueError, IndexError):
                return None
        
        return current_section
    
    def get_flat_sections(self) -> List[Section]:
        """Get all sections in reading order (flattened)"""
        flat_sections = []
        for section in self.sections:
            flat_sections.append(section)
            flat_sections.extend(self._get_subsections_recursive(section))
        return flat_sections
    
    def _get_subsections_recursive(self, section: Section) -> List[Section]:
        """Recursively get all subsections"""
        subsections = []
        for subsection in section.subsections:
            subsections.append(subsection)
            subsections.extend(self._get_subsections_recursive(subsection))
        return subsections
    
    def generate_toc(self) -> List[Dict[str, Any]]:
        """Generate table of contents from section hierarchy"""
        toc = []
        for section in self.sections:
            toc.append(self._section_to_toc_entry(section))
        self.table_of_contents = toc
        return toc
    
    def _section_to_toc_entry(self, section: Section) -> Dict[str, Any]:
        """Convert a section to a TOC entry"""
        entry = {
            "id": section.id,
            "title": section.header.html or "",
            "section_number": section.metadata.section_number,
            "depth_level": section.metadata.depth_level,
            "page_number": getattr(section.header, 'page_id', None),
            "has_subsections": len(section.subsections) > 0,
            "hierarchy": section.metadata.hierarchy_titles,
            "section_hash": section.section_hash
        }
        
        if section.subsections:
            entry["subsections"] = [
                self._section_to_toc_entry(subsec) 
                for subsec in section.subsections
            ]
        
        return entry
    
    def get_reading_order_blocks(self) -> List[Block]:
        """Get all blocks in reading order, preserving hierarchy"""
        blocks = []
        for section in self.sections:
            blocks.append(section.header)
            blocks.extend(section.get_ordered_content(include_subsections=True))
        return blocks

# Conversion utilities
def convert_flat_to_hierarchical(old_document) -> HierarchicalDocument:
    """Convert flat document structure to hierarchical"""
    # Implementation to convert existing documents
    pass