# Task 110: Verify and Fix Hierarchical JSON Export for ArangoDB ⏳ Not Started

**Objective**: Ensure Marker can export PDFs into the exact hierarchical JSON structure required by ArangoDB with all features working correctly.

**Requirements**:
1. Section hierarchy must be tracked and preserved
2. Document model must be accurate with proper metadata
3. Images must be described (when LLM is enabled)
4. JSON objects (tables, images, text) must be separate ordered objects within sections
5. Output must match exact ArangoDB JSON structure
6. All content must maintain proper ordering within sections

## Required JSON Structure (from ArangoDB analysis)

```json
{
  "document": {
    "id": "unique_document_id",
    "pages": [
      {
        "blocks": [
          {
            "type": "section_header|text|code|table|image|equation",
            "text": "content",
            "level": 1,  // for section_header
            "language": "python",  // for code
            "csv": "...",  // for tables
            "json": {...}  // for tables
          }
        ]
      }
    ]
  },
  "metadata": {
    "title": "Document Title",
    "filepath": "/path/to/original.pdf",
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
    "full_text": "Complete document text...",
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
```

## Implementation Tasks

### Task 1: Fix ArangoDB Renderer Issues ⏳ Not Started

**Priority**: HIGH | **Complexity**: MEDIUM | **Impact**: HIGH

**Implementation Steps**:
- [ ] 1.1 Fix import issues in marker/renderers/arangodb_json.py
  - Fix missing imports (os, time)
  - Fix BlockOutput duplicate definition
  - Ensure proper Pydantic model structure

- [ ] 1.2 Test basic ArangoDB rendering
  - Create simple test PDF
  - Run extraction with arangodb format
  - Verify output structure matches requirements

- [ ] 1.3 Fix recursion issues in section hierarchy
  - Debug the "maximum recursion depth exceeded" error
  - Implement proper section hierarchy extraction
  - Test with nested sections

### Task 2: Verify Section Hierarchy Tracking ⏳ Not Started

**Priority**: HIGH | **Complexity**: HIGH | **Impact**: HIGH

**Implementation Steps**:
- [ ] 2.1 Test section detection
  - Verify SectionHeader blocks are detected
  - Check heading_level attributes
  - Ensure proper parent-child relationships

- [ ] 2.2 Implement section context tracking
  - Track current section for each block
  - Maintain section hierarchy stack
  - Associate content blocks with their sections

- [ ] 2.3 Verify hierarchical structure in output
  - Ensure blocks are grouped by section
  - Verify section nesting is preserved
  - Check section ordering

### Task 3: Validate Document Model ⏳ Not Started

**Priority**: HIGH | **Complexity**: MEDIUM | **Impact**: HIGH

**Implementation Steps**:
- [ ] 3.1 Verify metadata extraction
  - Document title extraction
  - File metadata (path, size, etc.)
  - Processing metadata (time, engine, etc.)

- [ ] 3.2 Test block type mapping
  - Ensure all block types map correctly
  - Verify type names match ArangoDB expectations
  - Test special cases (equations, footnotes, etc.)

- [ ] 3.3 Validate content ordering
  - Blocks maintain reading order
  - Sections appear in correct sequence
  - Pages are properly ordered

### Task 4: Test Image Description Feature ⏳ Not Started

**Priority**: MEDIUM | **Complexity**: HIGH | **Impact**: MEDIUM

**Implementation Steps**:
- [ ] 4.1 Enable LLM image description
  - Configure LLM service
  - Enable image description processor
  - Test with sample images

- [ ] 4.2 Verify image block output
  - Image blocks have proper type
  - Description text is included
  - Image metadata is preserved

- [ ] 4.3 Test without LLM fallback
  - Ensure graceful degradation
  - Basic image detection works
  - Placeholder text when no LLM

### Task 5: Validate Table Extraction ⏳ Not Started

**Priority**: HIGH | **Complexity**: MEDIUM | **Impact**: HIGH

**Implementation Steps**:
- [ ] 5.1 Test table detection
  - Tables are properly identified
  - Table blocks have correct type
  - Table boundaries are accurate

- [ ] 5.2 Verify table data formats
  - Text representation is included
  - CSV format is generated
  - JSON structure is created

- [ ] 5.3 Test complex tables
  - Multi-column tables
  - Tables with merged cells
  - Tables spanning pages

### Task 6: Test Content Merging and Ordering ⏳ Not Started

**Priority**: HIGH | **Complexity**: MEDIUM | **Impact**: HIGH

**Implementation Steps**:
- [ ] 6.1 Verify text block merging
  - Adjacent text blocks are merged
  - Paragraph boundaries preserved
  - No over-merging across sections

- [ ] 6.2 Test object ordering
  - Reading order is maintained
  - Mixed content types ordered correctly
  - Section boundaries respected

- [ ] 6.3 Validate block separation
  - Tables remain separate objects
  - Images are individual blocks
  - Code blocks are preserved

### Task 7: Integration Testing ⏳ Not Started

**Priority**: CRITICAL | **Complexity**: LOW | **Impact**: CRITICAL

**Implementation Steps**:
- [ ] 7.1 Test with sample PDFs
  - data/input/2505.03335v2.pdf (academic paper)
  - data/input/Arango_AQL_Example.pdf (technical doc)
  - data/input/python-type-checking-readthedocs-io-en-latest.pdf (manual)

- [ ] 7.2 Validate complete output
  - All required fields present
  - Structure matches ArangoDB spec
  - Content is complete and accurate

- [ ] 7.3 Test ArangoDB import
  - Export JSON from Marker
  - Import into ArangoDB project
  - Verify successful ingestion

### Task 8: Create Comprehensive Test Suite ⏳ Not Started

**Priority**: MEDIUM | **Complexity**: MEDIUM | **Impact**: HIGH

**Implementation Steps**:
- [ ] 8.1 Unit tests for renderer
  - Test each output component
  - Verify field mappings
  - Check edge cases

- [ ] 8.2 Integration tests
  - End-to-end PDF conversion
  - Multiple document types
  - Performance benchmarks

- [ ] 8.3 Validation scripts
  - JSON schema validation
  - ArangoDB compatibility check
  - Content completeness verification

## Usage Examples

```bash
# Extract PDF to ArangoDB JSON format
marker extract-pdf data/input/test.pdf --format arangodb --output-dir output/

# With LLM enhancement for images
marker extract-pdf data/input/test.pdf --format arangodb --use-llm --output-dir output/

# Batch extraction
marker batch-extract data/input/ --format arangodb --output-dir output/
```

## Validation Checklist

- [ ] ArangoDB JSON structure matches specification exactly
- [ ] Section hierarchy is preserved and trackable
- [ ] All content types are properly separated
- [ ] Object ordering within sections is maintained
- [ ] Images have descriptions (with LLM)
- [ ] Tables have text, CSV, and JSON representations
- [ ] Metadata is complete and accurate
- [ ] Raw corpus includes all text content
- [ ] Output can be imported into ArangoDB successfully