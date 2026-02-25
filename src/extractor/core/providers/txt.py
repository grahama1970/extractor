"""
TXT Provider for Plain Text Files
----------------------------------
Extracts content from plain text files (.txt) into UnifiedDocument format.
Uses modular TXTStructureDetector for enhanced chapter/title detection.
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from extractor.core.schema.unified_document import (
    UnifiedDocument,
    SourceType,
    BaseBlock,
    BlockType,
    BlockMetadata,
    DocumentMetadata,
)
from extractor.core.providers.txt_structure_detector import (
    TXTStructureDetector, 
    create_detector
)
from loguru import logger


class TXTProvider:
    """Provider for plain text files with enhanced structure detection."""
    
    def __init__(self):
        self.detector = create_detector()
    
    def extract_document(self, filepath: Union[str, Path]) -> UnifiedDocument:
        """Extract content from TXT file with enhanced structure detection."""
        file_path = Path(filepath)
        logger.info(f"Extracting TXT: {file_path.name}")
        
        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try with latin-1 encoding
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
        
        # Detect structure
        structure_info = self.detector.detect_structure(content)
        logger.info(f"Detected structure type: {structure_info['structure_type']}")
        
        # Extract based on detected structure
        if structure_info['recommended_extraction'] == 'single_section':
            blocks = self._extract_single_section(content)
        elif structure_info['recommended_extraction'] == 'chapter_based':
            blocks = self._extract_with_chapters(content, structure_info['chapters'])
        elif structure_info['recommended_extraction'] == 'title_based':
            blocks = self._extract_with_titles(content, structure_info['titles'])
        else:
            blocks = self._extract_line_by_line(content)
        
        # Create document
        return UnifiedDocument(
            id=file_path.stem,
            source_type=SourceType.TXT,
            source_path=str(file_path),
            blocks=blocks,
            metadata=DocumentMetadata(
                title=file_path.stem,
                file_hash=self._compute_file_hash(file_path),
                page_count=1,  # Text files are single "page"
            )
        )
    
    def _extract_single_section(self, content: str) -> List[BaseBlock]:
        """Extract small files as a single section."""
        lines = content.split('\n')
        blocks = []
        block_id = 0
        
        for line_num, line in enumerate(lines):
            line = line.strip()
            if line:  # Skip empty lines
                block_id += 1
                blocks.append(
                    BaseBlock(
                        id=f"txt-block-{block_id:04d}",
                        type=BlockType.PARAGRAPH,
                        content=line,
                        metadata=BlockMetadata(
                            page_number=0,
                            bbox=[0, line_num * 20, 100, (line_num + 1) * 20],
                            attributes={
                                "line_number": line_num + 1,
                                "section": "Main Content"
                            }
                        )
                    )
                )
        
        return blocks
    
    def _extract_with_chapters(self, content: str, chapters: List) -> List[BaseBlock]:
        """Extract content using chapter-based structure."""
        blocks = []
        block_id = 0
        
        # Get chapter sections
        chapter_sections = self.detector.get_chapter_sections(content, chapters)
        
        for i, (chapter, section_content) in enumerate(zip(chapters, chapter_sections)):
            # Create chapter heading block
            block_id += 1
            blocks.append(
                BaseBlock(
                    id=f"txt-block-{block_id:04d}",
                    type=BlockType.HEADING,
                    content=chapter.text,
                    metadata=BlockMetadata(
                        page_number=0,
                        bbox=[0, chapter.line_number * 20, 100, (chapter.line_number + 1) * 20],
                        attributes={
                            "line_number": chapter.line_number,
                            "chapter_title": chapter.text,
                            "is_chapter_marker": True,
                            "confidence": chapter.confidence
                        }
                    )
                )
            )
            
            # Process content within the chapter
            lines = section_content.split('\n')
            for line_num, line in enumerate(lines):
                line = line.strip()
                if line and not any(pattern.match(line) for pattern in self.detector.chapter_patterns):
                    block_id += 1
                    blocks.append(
                        BaseBlock(
                            id=f"txt-block-{block_id:04d}",
                            type=BlockType.PARAGRAPH,
                            content=line,
                            metadata=BlockMetadata(
                                page_number=0,
                                bbox=[0, (chapter.line_number + line_num + 1) * 20, 100, (chapter.line_number + line_num + 2) * 20],
                                attributes={
                                    "line_number": chapter.line_number + line_num + 1,
                                    "chapter": chapter.text,
                                    "original_line_number": line_num + 1
                                }
                            )
                        )
                    )
        
        return blocks
    
    def _extract_with_titles(self, content: str, titles: List) -> List[BaseBlock]:
        """Extract content using title-based structure."""
        blocks = []
        block_id = 0
        
        # Get title sections
        title_sections = self.detector.get_title_sections(content, titles)
        
        for section_info in title_sections:
            title_text = section_info["title"]
            section_content = section_info["content"]
            
            # Find the title match for this section
            title_match = next((t for t in titles if t.text == title_text), None)
            if not title_match:
                continue
            
            # Create title heading block
            block_id += 1
            blocks.append(
                BaseBlock(
                    id=f"txt-block-{block_id:04d}",
                    type=BlockType.HEADING,
                    content=title_text,
                    metadata=BlockMetadata(
                        page_number=0,
                        bbox=[0, title_match.line_number * 20, 100, (title_match.line_number + 1) * 20],
                        attributes={
                            "line_number": title_match.line_number,
                            "title": title_text,
                            "is_title": True,
                            "confidence": title_match.confidence
                        }
                    )
                )
            )
            
            # Process content within the title section
            lines = section_content.split('\n')
            for line_num, line in enumerate(lines):
                line = line.strip()
                if line and line != title_text:  # Skip the title line itself
                    block_id += 1
                    blocks.append(
                        BaseBlock(
                            id=f"txt-block-{block_id:04d}",
                            type=BlockType.PARAGRAPH,
                            content=line,
                            metadata=BlockMetadata(
                                page_number=0,
                                bbox=[0, (title_match.line_number + line_num + 1) * 20, 100, (title_match.line_number + line_num + 2) * 20],
                                attributes={
                                    "line_number": title_match.line_number + line_num + 1,
                                    "section": title_text
                                }
                            )
                        )
                    )
        
        return blocks
    
    def _extract_line_by_line(self, content: str) -> List[BaseBlock]:
        """Fallback method for simple line-by-line extraction."""
        lines = content.split('\n')
        blocks = []
        block_id = 0
        
        for line_num, line in enumerate(lines):
            line = line.strip()
            if line:  # Skip empty lines
                block_id += 1
                blocks.append(
                    BaseBlock(
                        id=f"txt-block-{block_id:04d}",
                        type=BlockType.PARAGRAPH,
                        content=line,
                        metadata=BlockMetadata(
                            page_number=0,
                            bbox=[0, line_num * 20, 100, (line_num + 1) * 20],
                            attributes={"line_number": line_num + 1}
                        )
                    )
                )
        
        return blocks
    
    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute hash of the file content."""
        import hashlib
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""


def provider_from_filepath(file_path: Path) -> TXTProvider:
    """Factory function for TXT provider."""
    return TXTProvider()