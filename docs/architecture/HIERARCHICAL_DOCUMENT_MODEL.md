# Hierarchical Document Model

## Proposed Structure

```
Document
├── File Metadata (top level)
│   ├── filepath
│   ├── file_size
│   ├── file_hash
│   ├── creation_date
│   ├── modification_date
│   └── mime_type
│
├── Processing Metadata
│   ├── extraction_date
│   ├── extraction_duration
│   ├── processor_version
│   ├── ocr_engine
│   ├── quality_metrics
│   │   ├── ocr_confidence
│   │   ├── layout_confidence
│   │   └── completeness_score
│   └── errors_encountered
│
├── Document Metadata
│   ├── title
│   ├── author
│   ├── subject
│   ├── keywords
│   ├── language
│   ├── page_count
│   ├── document_summary
│   └── content_statistics
│       ├── total_sections
│       ├── total_words
│       ├── total_images
│       ├── total_tables
│       └── reading_time
│
└── Sections (hierarchical content)
    ├── Section 1
    │   ├── header
    │   ├── section_metadata
    │   │   ├── summary
    │   │   ├── key_points
    │   │   ├── word_count
    │   │   └── content_types
    │   ├── content_blocks
    │   │   ├── paragraph_1
    │   │   ├── image_1
    │   │   ├── table_1
    │   │   └── paragraph_2
    │   └── subsections
    │       ├── Section 1.1
    │       │   ├── header
    │       │   ├── section_metadata
    │       │   └── content_blocks
    │       └── Section 1.2
    │           ├── header
    │           ├── section_metadata
    │           └── content_blocks
    │
    └── Section 2
        ├── header
        ├── section_metadata
        ├── content_blocks
        └── subsections
```

## Implementation

```python
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

class FileMetadata(BaseModel):
    """File-level metadata"""
    filepath: Path
    file_size: int  # bytes
    file_hash: str  # SHA-256
    creation_date: Optional[datetime]
    modification_date: Optional[datetime]
    mime_type: str

class ProcessingMetadata(BaseModel):
    """Processing/extraction metadata"""
    extraction_date: datetime
    extraction_duration: float  # seconds
    processor_version: str
    ocr_engine: Optional[str]
    quality_metrics: Dict[str, float]
    errors_encountered: List[str]
    processing_config: Dict[str, Any]

class DocumentMetadata(BaseModel):
    """Document content metadata"""
    title: Optional[str]
    author: Optional[str]
    subject: Optional[str]
    keywords: List[str]
    language: str
    page_count: int
    document_summary: Optional[str]
    
    # Content statistics
    total_sections: int
    total_words: int
    total_images: int
    total_tables: int
    estimated_reading_time: int  # minutes

class SectionMetadata(BaseModel):
    """Section-specific metadata"""
    summary: Optional[str]
    key_points: List[str]
    word_count: int
    reading_time: int
    depth_level: int
    section_number: str  # e.g., "1.2.3"
    
    # Content analysis
    has_images: bool
    has_tables: bool
    has_equations: bool
    has_code: bool
    
    # Relationships
    parent_section_id: Optional[str]
    subsection_ids: List[str]

class Section(BaseModel):
    """A section with its content and subsections"""
    id: str
    header: SectionHeader
    metadata: SectionMetadata
    content_blocks: List[Block]  # Direct content of this section
    subsections: List['Section']  # Nested sections
    
    def get_all_content(self, include_subsections: bool = True) -> List[Block]:
        """Get all content blocks, optionally including subsections"""
        blocks = list(self.content_blocks)
        if include_subsections:
            for subsection in self.subsections:
                blocks.extend(subsection.get_all_content())
        return blocks
    
    def find_subsection(self, section_number: str) -> Optional['Section']:
        """Find a subsection by its number (e.g., '1.2.3')"""
        # Implementation here
        pass

class Document(BaseModel):
    """Complete document with all metadata and hierarchical sections"""
    # File information
    file_metadata: FileMetadata
    
    # Processing information
    processing_metadata: ProcessingMetadata
    
    # Document information
    document_metadata: DocumentMetadata
    
    # Content (hierarchical sections)
    sections: List[Section]
    
    # Optional: flat view for compatibility
    pages: Optional[List[PageGroup]] = None
    
    # Navigation helpers
    def get_section(self, section_id: str) -> Optional[Section]:
        """Get any section by ID, regardless of nesting"""
        # Recursive search implementation
        pass
    
    def get_section_by_number(self, section_number: str) -> Optional[Section]:
        """Get section by number like '1.2.3'"""
        pass
    
    def get_toc(self) -> List[Dict]:
        """Generate table of contents from section hierarchy"""
        pass
    
    def get_flat_sections(self) -> List[Section]:
        """Get all sections in reading order (flattened)"""
        pass
```

## Key Benefits

1. **Clear Hierarchy**: File → Processing → Document → Sections → Content
2. **Separation of Concerns**: Different types of metadata at appropriate levels
3. **Efficient Navigation**: Easy to traverse and find content
4. **Rich Context**: Metadata available at every level
5. **Backward Compatibility**: Can still provide flat views if needed

## Migration Path

1. Start with minimal changes to existing Document model
2. Add new fields gradually
3. Create adapters to convert between old and new formats
4. Update processors to populate new structure
5. Update renderers to output hierarchical JSON

This structure makes it much clearer what information belongs where and provides a natural way to navigate complex documents.