"""
Unified Section Summarizer Processor

This processor adds LLM-generated summaries to sections and the overall document.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from marker.processors import BaseProcessor
from marker.schema.document import Document
from marker.schema.blocks.sectionheader import SectionHeader
from marker.logger import logger
import litellm


class SectionSummarizer(BaseProcessor):
    """
    Processor that adds LLM-generated summaries to sections and documents.
    
    This processor:
    1. Identifies all SectionHeader blocks in the document
    2. Generates a summary for each section using LLM
    3. Adds an overall document summary based on section summaries
    """
    
    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.config = config or {}
        
        # Core settings
        self.model_name = self.config.get('model_name', 'gemini-2.0-flash-exp')
        self.max_section_length = self.config.get('max_section_length', 3000)
        self.temperature = self.config.get('temperature', 0.3)
        self.enabled = self.config.get('enabled', True)
    
    def __call__(self, document: Document) -> Document:
        """Process the document and add summaries to sections."""
        if not self.enabled:
            return document
            
        logger.info("Starting section summarization")
        
        try:
            # Find all sections
            sections = self._find_sections(document)
            if not sections:
                logger.info("No sections found to summarize")
                return document
            
            # Summarize each section
            section_summaries = []
            for section in sections:
                summary = self._summarize_section(document, section)
                if summary:
                    section.metadata['summary'] = summary
                    section_summaries.append(summary)
            
            # Create overall document summary
            if section_summaries:
                doc_summary = self._create_document_summary(section_summaries)
                document.metadata['document_summary'] = doc_summary
                
        except Exception as e:
            logger.error(f"Error during summarization: {e}")
            # Continue without failing the entire document processing
            
        return document
    
    def _find_sections(self, document: Document) -> List[SectionHeader]:
        """Find all section headers in the document."""
        sections = []
        for page in document.pages:
            for block in page.contained_blocks(document, [SectionHeader]):
                sections.append(block)
        return sections
    
    def _summarize_section(self, document: Document, section: SectionHeader) -> Optional[str]:
        """Generate summary for a single section."""
        try:
            # Get section content
            content = self._get_section_content(document, section)
            if not content or len(content.strip()) < 50:
                return None
                
            # Truncate if too long
            if len(content) > self.max_section_length:
                content = content[:self.max_section_length] + "..."
            
            # Generate summary
            prompt = f"Summarize the following section concisely:\n\n{content}"
            
            response = litellm.completion(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error summarizing section: {e}")
            return None
    
    def _get_section_content(self, document: Document, section: SectionHeader) -> str:
        """Extract text content for a section."""
        content_parts = []
        
        # Get section title
        content_parts.append(section.raw_text(document))
        
        # Find content blocks following this section
        page = next((p for p in document.pages if section in p.contained_blocks(document, [])), None)
        if not page:
            return section.raw_text(document)
            
        section_level = section.heading_level or 1
        found_section = False
        
        for block in page.children:
            if block == section:
                found_section = True
                continue
                
            if found_section:
                # Stop at next section of same or higher level
                if isinstance(block, SectionHeader):
                    next_level = block.heading_level or 1
                    if next_level <= section_level:
                        break
                
                # Collect content
                content_parts.append(block.raw_text(document))
        
        return "\n".join(content_parts)
    
    def _create_document_summary(self, section_summaries: List[str]) -> str:
        """Create overall document summary from section summaries."""
        try:
            combined = "\n\n".join(section_summaries)
            
            prompt = f"Create a concise overall summary from these section summaries:\n\n{combined}"
            
            response = litellm.completion(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=300
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error creating document summary: {e}")
            return "Document summary generation failed."