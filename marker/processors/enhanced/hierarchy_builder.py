"""
Processor to build hierarchical document structure from flat blocks
"""
from typing import List, Dict, Optional
import hashlib
from marker.processors import BaseProcessor
from marker.schema.document import Document
from marker.schema.blocks.sectionheader import SectionHeader
from marker.schema.blocks import Block
from marker.schema import BlockTypes
from marker.schema.enhanced_document import (
    HierarchicalDocument, 
    Section, 
    FileMetadata, 
    ProcessingMetadata, 
    DocumentMetadata, 
    SectionMetadata
)
import logging
from pathlib import Path
import os

logger = logging.getLogger(__name__)

class HierarchyBuilder(BaseProcessor):
    """
    Processor that transforms flat document structure into hierarchical sections
    while preserving block order within sections
    """
    
    def __call__(self, document: Document) -> Document:
        """Build hierarchical structure and attach to document"""
        logger.info("Building hierarchical document structure")
        
        # Create hierarchical document
        hierarchical_doc = self._build_hierarchy(document)
        
        # Attach to original document metadata
        if not hasattr(document, 'metadata') or document.metadata is None:
            document.metadata = {}
        
        document.metadata['hierarchical_structure'] = hierarchical_doc
        
        # Add section summaries to metadata if available
        if hasattr(document, 'metadata') and 'section_summaries' in document.metadata:
            self._attach_summaries(hierarchical_doc, document.metadata['section_summaries'])
        
        return document
    
    def _build_hierarchy(self, document: Document) -> HierarchicalDocument:
        """Build the hierarchical document structure"""
        # Create file metadata
        file_metadata = FileMetadata(
            filepath=Path(document.filepath),
            file_size=os.path.getsize(document.filepath) if os.path.exists(document.filepath) else 0,
            file_hash=self._compute_file_hash(document.filepath),
            mime_type="application/pdf"
        )
        
        # Create processing metadata
        processing_metadata = ProcessingMetadata(
            processor_version="1.0.0",
            processing_config={}
        )
        
        # Create document metadata
        doc_metadata = DocumentMetadata(
            page_count=len(document.pages),
            language="en"  # Could be detected
        )
        
        # Create hierarchical document
        hierarchical_doc = HierarchicalDocument(
            file_metadata=file_metadata,
            processing_metadata=processing_metadata,
            document_metadata=doc_metadata
        )
        
        # Process pages and build sections
        current_section: Optional[Section] = None
        section_stack: List[Section] = []  # Stack for nested sections
        
        for page in document.pages:
            self._process_page_blocks(
                page, 
                hierarchical_doc, 
                current_section, 
                section_stack,
                document
            )
        
        # Generate table of contents
        hierarchical_doc.generate_toc()
        
        # Update document statistics
        self._update_statistics(hierarchical_doc)
        
        return hierarchical_doc
    
    def _process_page_blocks(
        self, 
        page, 
        hierarchical_doc: HierarchicalDocument,
        current_section: Optional[Section],
        section_stack: List[Section],
        document: Document
    ):
        """Process blocks on a page, maintaining order and building sections"""
        for block in page.children:
            if isinstance(block, SectionHeader):
                # Create new section
                new_section = self._create_section(block, document)
                
                # Determine parent based on heading level
                parent_section = self._find_parent_section(
                    new_section, 
                    section_stack, 
                    block.heading_level
                )
                
                # Add to hierarchy
                hierarchical_doc.add_section(new_section, parent_section)
                
                # Update stack
                self._update_section_stack(
                    section_stack, 
                    new_section, 
                    block.heading_level
                )
                
                current_section = new_section
                
            else:
                # Add content block to current section
                if current_section:
                    current_section.add_content_block(block)
                else:
                    # No section yet, might want to create a default section
                    logger.warning(f"Block {block.id} found before any section")
    
    def _create_section(self, header: SectionHeader, document: Document) -> Section:
        """Create a section from a section header"""
        section = Section(
            id=f"section_{header.page_id}_{header.block_id}",
            header=header,
            metadata=SectionMetadata(
                depth_level=0,  # Will be set when added to hierarchy
                section_number=""  # Will be set when added to hierarchy
            )
        )
        
        # Compute section hash if not already present
        if not header.section_hash:
            section.section_hash = section.compute_section_hash()
        else:
            section.section_hash = header.section_hash
        
        return section
    
    def _find_parent_section(
        self, 
        new_section: Section, 
        section_stack: List[Section], 
        heading_level: Optional[int]
    ) -> Optional[Section]:
        """Find the appropriate parent section based on heading level"""
        if not section_stack or heading_level is None:
            return None
        
        # Find parent with lower heading level
        for section in reversed(section_stack):
            if section.header.heading_level is not None and \
               section.header.heading_level < heading_level:
                return section
        
        return None
    
    def _update_section_stack(
        self, 
        section_stack: List[Section], 
        new_section: Section, 
        heading_level: Optional[int]
    ):
        """Update the section stack for tracking hierarchy"""
        if heading_level is None:
            return
        
        # Remove sections with same or higher level
        while section_stack:
            last_section = section_stack[-1]
            if (last_section.header.heading_level is None or 
                last_section.header.heading_level >= heading_level):
                section_stack.pop()
            else:
                break
        
        section_stack.append(new_section)
    
    def _compute_file_hash(self, filepath: str) -> str:
        """Compute SHA-256 hash of file"""
        if not os.path.exists(filepath):
            return ""
        
        try:
            sha256_hash = hashlib.sha256()
            with open(filepath, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Error computing file hash: {e}")
            return ""
    
    def _update_statistics(self, hierarchical_doc: HierarchicalDocument):
        """Update document statistics"""
        total_words = 0
        total_images = 0
        total_tables = 0
        
        for section in hierarchical_doc.get_flat_sections():
            total_words += section.metadata.word_count
            total_images += section.metadata.image_count
            total_tables += section.metadata.table_count
        
        hierarchical_doc.document_metadata.total_words = total_words
        hierarchical_doc.document_metadata.total_images = total_images
        hierarchical_doc.document_metadata.total_tables = total_tables
        
        # Estimate reading time (200 words per minute)
        hierarchical_doc.document_metadata.estimated_reading_time = max(1, total_words // 200)
    
    def _attach_summaries(
        self, 
        hierarchical_doc: HierarchicalDocument, 
        section_summaries: List[Dict]
    ):
        """Attach summaries to sections if available"""
        # Create a mapping of section IDs to summaries
        summary_map = {
            summary['section_id']: summary['summary'] 
            for summary in section_summaries
        }
        
        # Attach summaries to sections
        for section in hierarchical_doc.get_flat_sections():
            section_id = f"/page/{section.header.page_id}/SectionHeader/{section.header.block_id}"
            if section_id in summary_map:
                section.metadata.summary = summary_map[section_id]
        
        # Attach document summary if available
        for summary in section_summaries:
            if 'document_summary' in summary:
                hierarchical_doc.document_metadata.document_summary = summary['document_summary']
                break

class SectionContentAnalyzer(BaseProcessor):
    """
    Additional processor to analyze section content and update metadata
    """
    
    def __call__(self, document: Document) -> Document:
        """Analyze section content and update metadata"""
        if not hasattr(document, 'metadata') or 'hierarchical_structure' not in document.metadata:
            logger.warning("No hierarchical structure found, skipping content analysis")
            return document
        
        hierarchical_doc = document.metadata['hierarchical_structure']
        
        for section in hierarchical_doc.get_flat_sections():
            self._analyze_section_content(section)
        
        return document
    
    def _analyze_section_content(self, section: Section):
        """Analyze content of a section and update metadata"""
        word_count = 0
        
        for block in section.content_blocks:
            # Count words
            if hasattr(block, 'html') and block.html:
                word_count += len(block.html.split())
            elif hasattr(block, 'text') and block.text:
                word_count += len(block.text.split())
            
            # Check content types
            if block.block_type == BlockTypes.Equation:
                section.metadata.has_equations = True
            elif block.block_type == BlockTypes.Code:
                section.metadata.has_code = True
        
        section.metadata.word_count = word_count
        section.metadata.reading_time = max(1, word_count // 200)  # 200 words/minute