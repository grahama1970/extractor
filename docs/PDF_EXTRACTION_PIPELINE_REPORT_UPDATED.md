# PDF Extraction Pipeline - Current Implementation

## Overview

The extractor project is a sophisticated PDF extraction system that produces structured JSON output matching a gold standard format. The pipeline includes:

- Multi-strategy extraction (Marker, PyMuPDF fallback, OCR)
- Hierarchical document structure building
- Block type classification and verification
- Section header detection and numbering
- Figure description generation
- Table processing and merging
- Multiple output formats (Gold Standard, ArangoDB)

## Current Pipeline Architecture

### Entry Points

1. **`pipeline_orchestrator.py`** - Main orchestration logic
2. **`unified_extractor.py`** - Core extraction with fallback strategies
3. **`pipeline_config.py`** - Configuration-driven processing pipeline

## Pipeline Stages (6-Step Process)

### Step 1: Marker Extraction
**Processor:** `MARKER_EXTRACTION`
**File:** Handled internally by marker library
**Purpose:** Extract raw blocks from PDF using Surya OCR models

```python
ProcessorConfig(
    name="step1_marker_extraction",
    type=ProcessorType.MARKER_EXTRACTION,
    settings={
        "use_llm": True,
        "llm_model": "vertex_ai/gemini-2.5-flash",
        "output_format": "json"
    }
)
```

### Step 2: Text Cleaning
**Processor:** `TEXT_CLEANING`
**File:** `src/extractor/core/processors/text.py`
**Purpose:** Clean and normalize extracted text

```python
ProcessorConfig(
    name="step2_text_cleaning",
    type=ProcessorType.TEXT_CLEANING,
    settings={
        "remove_unicode_marks": True,
        "normalize_whitespace": True,
        "fix_encoding": True
    }
)
```

### Step 3: Block Verification
**Processor:** `BLOCK_VERIFICATION`
**File:** `src/extractor/core/processors/block_verification.py`
**Purpose:** Fix mislabeled blocks using suspicious header detection

```python
ProcessorConfig(
    name="step3_block_verification",
    type=ProcessorType.BLOCK_VERIFICATION,
    settings={
        "mode": "suspicious_only",
        "use_annotation_rules": True,
        "use_llm_verification": False,
        "llm_confidence_threshold": 0.85
    }
)
```

### Step 4: Hierarchy Building
**Processor:** `HIERARCHY_BUILDER`
**File:** `src/extractor/core/processors/enhanced/hierarchy_builder.py`
**Purpose:** Build document hierarchy and add gold standard fields

```python
ProcessorConfig(
    name="step4_hierarchy_builder",
    type=ProcessorType.HIERARCHY_BUILDER,
    settings={
        "add_breadcrumbs": True,
        "merge_contiguous_text": True
    }
)
```

This processor adds critical gold standard fields:
- `section_titles`: List of section headers in hierarchy
- `section_hashes`: MD5 hashes of section titles
- `section_number`: Hierarchical numbering (e.g., "4.1.5.4")
- `section_level`: Depth in hierarchy (0-based)

### Step 5: Output Rendering
**Processor:** `OUTPUT_RENDERER`
**File:** `src/extractor/core/output/gold_standard.py`
**Purpose:** Render final output in requested formats

### Step 6: Pipeline Report
**Processor:** Built into orchestrator
**Purpose:** Generate verification report

## Extraction Flow

```
┌─────────────────────┐
│    PDF Input        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ unified_extractor   │ ← Multiple strategies:
│ extract_to_unified  │   1. Marker (primary)
│      _json()        │   2. PyMuPDF (fallback)
└──────────┬──────────┘   3. OCR (last resort)
           │
           ▼
┌─────────────────────┐
│ extract_blocks_     │ ← Recursive extraction
│   recursive()       │   Handles nested structures
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  process_blocks()   │ ← Classification:
│                     │   - SectionHeader
│                     │   - Text
│                     │   - Figure
│                     │   - Table
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ merge_contiguous_   │ ← Text block merging
│   text_blocks()     │   Same-page consolidation
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ merge_split_tables  │ ← Table merging
│   _with_pandas()    │   Cross-page tables
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ create_gold_        │ ← Format conversion
│ standard_output()   │   Add metadata
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Gold Standard      │
│  JSON Output        │
└─────────────────────┘
```

## Key Components

### 1. Block Types
- **SectionHeader**: Document section headers
- **Text**: Regular text content
- **Figure**: Images with captions and descriptions
- **Table**: Tabular data (HTML and JSON formats)
- **Equation**: Mathematical equations
- **Code**: Code blocks
- **List**: Bulleted/numbered lists

### 2. Fallback Strategies

**PyMuPDF Fallback** (`extract_with_pymupdf`):
- Used when Marker fails
- Removes annotations
- Renders pages as images
- Re-processes with Marker

**OCR Fallback**:
- Last resort for corrupted PDFs
- Direct text extraction

### 3. Table Processing

**Pandas Integration**:
- Detects split tables across pages
- Merges based on column compatibility
- Preserves structure and data

**LLM Enhancement**:
- Table structure verification
- Header correction
- Data cleaning

### 4. Figure Processing

**Image Description Generation**:
- LLM-based descriptions
- Caption extraction
- Semantic understanding

## Output Formats

### Gold Standard Format
```json
{
  "sections": [{
    "section_id": 0,
    "blocks": [{
      "block_type": "SectionHeader",
      "text": "4.1.5.4. BHT (Branch History Table) submodule",
      "page": 0,
      "section_titles": ["BHT (Branch History Table) submodule"],
      "section_hashes": ["1402d30f1a7ebbc4e5645fc6234aedff"],
      "section_number": "4.1.5.4",
      "section_level": 3
    }]
  }],
  "summary": {
    "sections": 1,
    "text_blocks": 3,
    "figures": 1,
    "tables": 1
  }
}
```

### ArangoDB Format
```json
{
  "vertices": {
    "documents": [{...}],
    "sections": [{...}],
    "blocks": [{...}]
  },
  "edges": {
    "contains": [{...}],
    "follows": [{...}]
  }
}
```

## Current Limitations

1. **ArangoDB Integration**: Currently outputs ArangoDB format but doesn't query for learned patterns (unlike the corrected report suggested)
2. **Figure Descriptions**: Requires LLM integration for semantic descriptions
3. **Table Merging**: Basic pandas merging, could benefit from more sophisticated analysis
4. **Block Ordering**: No semantic reordering (figures after "following figure" references)

## Configuration-Driven Processing

The pipeline uses `PipelineConfig` to define processing steps:

```python
config = PipelineConfig.default_config(pdf_path)
# or
config = PipelineConfig.load(Path("config.json"))
```

Each processor can be enabled/disabled and configured independently, allowing for flexible pipeline customization.

## Error Handling

- Each extraction strategy has its own try-catch
- Fallback progression: Marker → PyMuPDF → OCR
- Detailed logging at each stage
- Graceful degradation on failures

## Performance Considerations

- Text block merging reduces redundancy
- Table merging prevents split data
- Configurable LLM usage for cost control
- Caching support (when enabled)

This updated report reflects the actual current implementation of the PDF extraction pipeline.