# Document Model Improvements

## Current Issues

1. **Section Hierarchy Not Properly Represented**: Sections are currently just SectionHeader blocks among other blocks, not parent nodes
2. **Limited Metadata Structure**: Metadata is just a generic dict
3. **No Explicit Section Relationships**: No clear parent-child relationships between sections and their content
4. **No Document-Level Properties**: Missing useful document-level metadata

## Proposed Improvements

### 1. Enhanced Document Metadata Structure

```python
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel

class DocumentMetadata(BaseModel):
    """Structured metadata for documents"""
    # Summary information
    document_summary: Optional[str] = None
    section_summaries: List[Dict[str, Any]] = []
    
    # Document properties
    title: Optional[str] = None
    author: Optional[str] = None
    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None
    page_count: int = 0
    language: Optional[str] = None
    
    # Extraction metadata
    extraction_date: datetime = datetime.now()
    extraction_method: str = "marker"
    extraction_version: Optional[str] = None
    extraction_duration: Optional[float] = None
    
    # Quality metrics
    ocr_confidence: Optional[float] = None
    table_count: int = 0
    image_count: int = 0
    section_count: int = 0
    
    # Content structure
    has_table_of_contents: bool = False
    has_index: bool = False
    has_bibliography: bool = False
    
    # Custom metadata
    custom: Dict[str, Any] = {}
```

### 2. Section as Container/Parent Node

Currently sections are not true parent nodes. We should add:

```python
class Section(BaseModel):
    """A section container that groups related content"""
    header: SectionHeader
    content_blocks: List[Block] = []
    subsections: List['Section'] = []
    
    # Section metadata
    section_number: Optional[str] = None  # e.g., "1.2.3"
    depth_level: int = 0  # nesting depth
    parent_section_id: Optional[str] = None
    
    # Summary and analysis
    summary: Optional[str] = None
    key_topics: List[str] = []
    word_count: int = 0
    
    # Navigation
    previous_section_id: Optional[str] = None
    next_section_id: Optional[str] = None
```

### 3. Enhanced Section Metadata

```python
class SectionMetadata(BaseModel):
    """Rich metadata for sections"""
    summary: Optional[str] = None
    
    # Content analysis
    key_points: List[str] = []
    mentioned_entities: List[str] = []  # People, places, organizations
    references: List[str] = []  # Citations, footnotes
    
    # Structure
    subsection_count: int = 0
    figure_count: int = 0
    table_count: int = 0
    equation_count: int = 0
    
    # Reading metrics
    estimated_reading_time: Optional[int] = None  # seconds
    complexity_score: Optional[float] = None
    
    # Relationships
    related_sections: List[str] = []  # IDs of related sections
    depends_on: List[str] = []  # Prerequisite sections
```

### 4. Document Structure Improvements

```python
class Document(BaseModel):
    filepath: str
    pages: List[PageGroup]
    sections: List[Section] = []  # Add explicit section hierarchy
    
    # Enhanced metadata
    metadata: DocumentMetadata
    
    # Document structure
    table_of_contents: Optional[TableOfContents] = None
    bibliography: Optional[Bibliography] = None
    index: Optional[Index] = None
    
    # Navigation helpers
    section_map: Dict[str, Section] = {}  # Quick lookup by ID
    
    def get_section_hierarchy(self) -> Dict:
        """Return nested dict of section structure"""
        pass
    
    def get_section_by_path(self, path: str) -> Optional[Section]:
        """Get section by path like '1.2.3'"""
        pass
```

### 5. Additional Metadata to Consider

1. **Content Categorization**:
   - Document type (research paper, report, manual, etc.)
   - Subject classification
   - Keywords/tags

2. **Quality Metrics**:
   - OCR accuracy scores
   - Layout detection confidence
   - Completeness score

3. **Processing History**:
   - Processing pipeline used
   - Errors encountered
   - Manual corrections made

4. **Semantic Information**:
   - Named entities extracted
   - Key concepts identified
   - Cross-references mapped

5. **Accessibility**:
   - Reading level
   - Language complexity
   - Alternative text availability

## Implementation Plan

1. Create structured metadata classes
2. Refactor section handling to use container model
3. Update processors to populate rich metadata
4. Add navigation and hierarchy methods
5. Update renderers to output structured metadata

## Benefits

1. **Better Organization**: Clear parent-child relationships
2. **Richer Context**: More metadata for downstream processing
3. **Improved Navigation**: Easy section traversal
4. **Better Search**: More fields to search/filter
5. **Quality Tracking**: Metrics for confidence and accuracy
6. **Semantic Understanding**: Relationships between sections

Would you like me to start implementing any of these improvements?