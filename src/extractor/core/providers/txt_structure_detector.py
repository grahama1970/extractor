"""
TXT Structure Detector
----------------------
Utility for detecting chapters, titles, and sections in plain text files.
Provides modular, debuggable structure detection for TXT providers.
"""

import re
from typing import List, Dict, Any, Optional, NamedTuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class StructureMatch:
    """Represents a detected structure element."""
    text: str
    start_pos: int
    end_pos: int
    line_number: int
    match_type: str  # 'chapter', 'title', 'section'
    confidence: float


class TXTStructureDetector:
    """Detects structural elements in plain text files."""
    
    def __init__(self):
        # Chapter/section detection patterns
        self.chapter_patterns = [
            re.compile(r"^\s*(Chapter\s+(?:\w+|[0-9]+))\s*$", re.IGNORECASE | re.MULTILINE),
            re.compile(r"^\s*(Prologue|Epilogue)\s*$", re.IGNORECASE | re.MULTILINE),
            re.compile(r"^\s*(Part\s+(?:\w+|[0-9]+))\s*$", re.IGNORECASE | re.MULTILINE),
        ]
        
        # Title detection patterns
        self.title_patterns = [
            # 1-5 words starting with capital letter, reasonable length
            re.compile(r"^\s*([A-Z][a-zA-Z\s]{1,60}?)\s*$", re.MULTILINE),
            # Roman numerals as titles
            re.compile(r"^\s*([IVXLCDM]+\.?\s+[A-Za-z]+.*?)\s*$", re.MULTILINE),
        ]
        
        # Section divider patterns
        self.divider_patterns = [
            re.compile(r"^\s*[-=]{3,}\s*$"),  # Lines of dashes or equals
            re.compile(r"^\s*[*#]{3,}\s*$"),  # Lines of asterisks or hashes
        ]
    
    def detect_structure(self, content: str) -> Dict[str, Any]:
        """
        Detect all structural elements in the content.
        
        Returns:
            Dict with keys:
            - 'has_chapters': bool
            - 'has_titles': bool
            - 'chapters': List[StructureMatch]
            - 'titles': List[StructureMatch]
            - 'structure_type': str ('chapters', 'titles', 'simple', 'small')
            - 'recommended_extraction': str
        """
        logger.info("Detecting structure in TXT content")
        
        # Basic content analysis
        lines = content.split('\n')
        non_empty_lines = [line.strip() for line in lines if line.strip()]
        
        # Check if file is small (treat as single section) - use a higher threshold for chapter detection
        # But allow chapter detection even in smaller files if chapters are present
        if len(non_empty_lines) <= 5:
            logger.info("Small file detected (<= 5 lines)")
            return {
                'has_chapters': False,
                'has_titles': False,
                'chapters': [],
                'titles': [],
                'structure_type': 'small',
                'recommended_extraction': 'single_section'
            }
        
        # Detect chapters
        chapters = self._detect_chapters(content)
        if len(chapters) > 1:  # Need at least 2 chapters to be meaningful
            logger.info(f"Detected {len(chapters)} chapters")
            return {
                'has_chapters': True,
                'has_titles': False,
                'chapters': chapters,
                'titles': [],
                'structure_type': 'chapters',
                'recommended_extraction': 'chapter_based'
            }
        
        # Detect titles
        titles = self._detect_titles(content)
        if len(titles) > 0 and len(titles) < 5:  # Reasonable number of titles
            logger.info(f"Detected {len(titles)} titles")
            return {
                'has_chapters': False,
                'has_titles': True,
                'chapters': [],
                'titles': titles,
                'structure_type': 'titles',
                'recommended_extraction': 'title_based'
            }
        
        # Fall back to simple extraction
        logger.info("No clear structure detected, using simple extraction")
        return {
            'has_chapters': False,
            'has_titles': False,
            'chapters': [],
            'titles': [],
            'structure_type': 'simple',
            'recommended_extraction': 'line_by_line'
        }
    
    def _detect_chapters(self, content: str) -> List[StructureMatch]:
        """Detect chapter markers in content."""
        chapters = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue
            
            for pattern in self.chapter_patterns:
                match = pattern.match(line_stripped)
                if match:
                    # Calculate position in original content
                    pos = sum(len(lines[i]) + 1 for i in range(line_num))  # +1 for newlines
                    
                    chapters.append(StructureMatch(
                        text=match.group(1),
                        start_pos=pos,
                        end_pos=pos + len(line),
                        line_number=line_num + 1,
                        match_type='chapter',
                        confidence=0.9
                    ))
                    break
        
        return chapters
    
    def _detect_titles(self, content: str) -> List[StructureMatch]:
        """Detect title markers in content."""
        titles = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue
            
            # Skip if it looks like a chapter (already detected)
            if any(pattern.match(line_stripped) for pattern in self.chapter_patterns):
                continue
            
            for pattern in self.title_patterns:
                match = pattern.match(line_stripped)
                if match:
                    title_text = match.group(1).strip()
                    
                    # Additional heuristics for title detection
                    if self._is_likely_title(title_text, line_stripped):
                        # Calculate position in original content
                        pos = sum(len(lines[i]) + 1 for i in range(line_num))  # +1 for newlines
                        
                        titles.append(StructureMatch(
                            text=title_text,
                            start_pos=pos,
                            end_pos=pos + len(line),
                            line_number=line_num + 1,
                            match_type='title',
                            confidence=0.7
                        ))
                        break
        
        return titles
    
    def _is_likely_title(self, title_text: str, original_line: str) -> bool:
        """Apply additional heuristics to determine if text is likely a title."""
        # Basic checks
        if len(title_text) < 3 or len(title_text) > 80:
            return False
        
        words = title_text.split()
        if len(words) < 1 or len(words) > 8:  # 1-8 words
            return False
        
        # Check capitalization pattern (at least 50% capitalized words)
        capitalized_words = sum(1 for word in words if word and word[0].isupper())
        if capitalized_words / len(words) < 0.5:
            return False
        
        # Check if it's all caps (might be a header)
        if title_text.isupper() and len(words) <= 5:
            return True
        
        # Check for common title patterns
        if any(word in title_text.lower() for word in ['introduction', 'conclusion', 'summary', 'overview']):
            return True
        
        return True  # Default to True if basic checks pass
    
    def get_chapter_sections(self, content: str, chapters: List[StructureMatch]) -> List[str]:
        """Split content into sections based on chapter boundaries."""
        if not chapters:
            return [content]
        
        sections = []
        content_pos = 0
        
        for i, chapter in enumerate(chapters):
            start_pos = chapter.start_pos
            
            # Get content from previous position to this chapter
            if i == 0:
                # Include content before first chapter
                section_content = content[content_pos:start_pos]
            else:
                # Content from previous chapter to this chapter
                section_content = content[content_pos:start_pos]
            
            if section_content.strip():
                sections.append(section_content)
            
            content_pos = start_pos
        
        # Add final section (after last chapter)
        final_section = content[content_pos:]
        if final_section.strip():
            sections.append(final_section)
        
        return sections
    
    def get_title_sections(self, content: str, titles: List[StructureMatch]) -> List[Dict[str, str]]:
        """Split content into sections based on title boundaries."""
        if not titles:
            return [{"title": "Main Content", "content": content}]
        
        sections = []
        content_pos = 0
        
        for i, title in enumerate(titles):
            start_pos = title.start_pos
            title_text = title.text
            
            # Get content from previous position to this title
            if i == 0:
                # Include content before first title
                section_content = content[content_pos:start_pos]
                if section_content.strip():
                    sections.append({"title": "Introduction", "content": section_content})
            
            # Find end position (next title or end of content)
            if i < len(titles) - 1:
                end_pos = titles[i + 1].start_pos
            else:
                end_pos = len(content)
            
            section_content = content[start_pos:end_pos]
            if section_content.strip():
                sections.append({"title": title_text, "content": section_content})
            
            content_pos = end_pos
        
        return sections


def create_detector() -> TXTStructureDetector:
    """Factory function for TXT structure detector."""
    return TXTStructureDetector()