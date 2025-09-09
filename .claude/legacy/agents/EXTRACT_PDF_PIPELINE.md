# PDF Extraction Pipeline: Complete Steps & Code References

## Overview
This pipeline converts PDFs with reviewer annotations into clean, structured sections ready for ArangoDB insertion.

## Phase 1: PDF Analysis & Raw Extraction

### Stage 1: Extract Reviewer Annotations
**Purpose**: Extract human reviewer annotations that guide extraction priorities
**Code**: `extractor.core.processors.gold_standard_annotation_extractor`
**Input**: `doc.pdf` (original PDF with annotations)
**Output**: `annotations.json`
```json
{
  "annotations": [
    {"type": "merge_table", "page": 0, "bbox": [72, 575, 202, 588], "content": "Single-row table should be text"},
    {"type": "section_header_correction", "page": 1, "bbox": [69.75, 536, 215, 552], "content": "For any HW configuration,"}
  ]
}
```

### Stage 2: Interpret Annotations Semantically
**Purpose**: Use Claude to understand what annotations mean for extraction strategy
**Code**: `claude -p` with prompt in `extract_pdf_pipeline.py:334-358`
**Input**: `annotations.json`
**Output**: Semantic interpretation (not saved to file)
**Example**: "The 'merge_table' annotations indicate fragmented tables that need reconstruction"

### Stage 3: Create Clean PDF
**Purpose**: Remove annotations/watermarks for cleaner extraction
**Code**: `extractor.core.processors.pdf_cleaner`
**Input**: `doc.pdf`
**Output**: `clean.pdf`

### Stage 4: Check Knowledge Base
**Purpose**: Find similar PDF patterns for better extraction
**Code**: `claude -p` with prompt in `extract_pdf_pipeline.py:380-407`
**Input**: PDF metadata
**Output**: Known patterns (not saved to file)

### Stage 5: Run Marker Extraction
**Purpose**: Extract all blocks (text, tables, figures) from clean PDF
**Code**: `extractor.core.scripts.convert_single` (marker library)
**Input**: `clean.pdf`
**Output**: `blocks.json`
```json
{
  "blocks": [
    {"block_type": "SectionHeader", "text": "4.1.5.4. BHT (Branch History Table) submodule", "page": 0},
    {"block_type": "Text", "text": "BHT is implemented as a memory...", "page": 0},
    {"block_type": "Table", "text": "FRONT\\nEND", "page": 1}  // Misidentified!
  ]
}
```

## Phase 2: Block Analysis & Correction

### Stage 5.1: Transform to Stage 2 Gold Standard Format
**Purpose**: Convert marker output to gold standard structure for validation
**Code**: `extractor.core.processors.marker_to_gold_standard`
**Input**: `blocks.json`
**Output**: `stage2_marker.json`

### Stage 5.5a: Identify Suspicious Blocks
**Purpose**: Use heuristics to find potentially misclassified blocks
**Code**: `extractor.core.processors.suspicious_block_analyzer`
**Heuristics**:
- Headers ending with comma: `text.endswith(',')`
- Too short headers: `len(text) < 5`
- Patterns like "For any", "As DebugEn"
- Single uppercase words not at left margin
**Input**: `blocks.json`
**Output**: `suspicious_analysis.json`
```json
{
  "suspicious_blocks": [
    {"index": 27, "block": {"text": "FRONT", "type": "SectionHeader"}, "issues": ["single_uppercase_word", "not_at_left_margin"]}
  ]
}
```

### Stage 5.5b: Batch Suspicious Blocks
**Purpose**: Group suspicious blocks for efficient Claude processing
**Code**: `extractor.core.processors.suspicious_block_batcher`
**Input**: `suspicious_analysis.json`
**Output**: `batches.json`

### Stage 5.5c: Fix Suspicious Blocks with Claude
**Purpose**: Use Claude to analyze suspicious blocks with ±2 context blocks
**Code**: `claude -p` batches in `extract_pdf_pipeline.py:514-543`
**Input**: Each batch with context blocks
**Output**: `fixed_blocks.json`
**Claude Prompt**:
```
Analyze these suspicious PDF blocks:
Block 27: Type: SectionHeader, Text: "FRONT", Page: 1
Previous Block: Type: Table, Text: "...TE"
Next Block: Type: TableCell, Text: "END"

Determine: Is this a real section header or table cell fragment?
```

## Phase 3: Section Building & Validation

### Stage 6: Build Section Hierarchy
**Purpose**: Group blocks into logical sections
**Code**: `extractor.core.processors.section_builder`
**Input**: `blocks.json` (or fixed blocks)
**Output**: `sections.json`
```json
{
  "sections": [
    {"section_id": "section_0", "title": "4.1.5.4. BHT...", "blocks": [...]},
    {"section_id": "section_7", "title": "FRONT", "blocks": [...]}  // Still has garbage!
  ]
}
```

### Stage 6.1: Transform to Stage 3 Gold Standard Format
**Purpose**: Convert sections to gold standard structure
**Code**: `extractor.core.processors.sections_to_gold_standard`
**Input**: `sections.json`, `blocks.json`
**Output**: `stage3_sections.json`

### Stage 6.5: Validate Sections with Claude (CRITICAL - OFTEN MISSING!)
**Purpose**: Identify and remove garbage sections like "FRONT", "END"
**Code**: Should be added after Stage 6.1
**Process**:
1. Extract sections with suspicious titles
2. Send to Claude with full section content
3. Claude determines if real section or table fragment
**Input**: `sections.json`
**Output**: `validated_sections.json`

## Phase 4: Enhancement & Enrichment

### Stage 7: Create Validation Images
**Purpose**: Generate visual snapshots for validation
**Code**: 
- `extractor.core.processors.pdf_snapshot`
- `extractor.core.processors.table_image_creator`
**Input**: `clean.pdf`, `sections.json`
**Output**: `snapshots/`, `table_images/`

### Stage 8: Enrich Sections
**Purpose**: Add metadata, cross-references, relationships
**Code**: `extractor.core.processors.stage7_enrichment_orchestrator`
**Input**: `sections.json`, `clean.pdf`, `blocks.json`, `annotations.json`
**Output**: `enriched_sections.json`

### Stage 9: Enhance Sections with Claude
**Purpose**: Clean content, fix formatting, merge fragments
**Code**: `claude -p` per section in `extract_pdf_pipeline.py:644-786`
**Input**: Each section file
**Output**: `enhanced_sections/enhanced_*.json`
**Claude Tasks**:
- Fix text spacing
- Merge fragmented blocks
- Reconstruct tables
- Generate figure captions

### Stage 10: Validate Against Gold Standard
**Purpose**: Compare final output to expected structure
**Code**: `extractor.core.processors.gold_validator`
**Input**: `merged_enhanced_sections.json`, `gold_standard_section_json.json`
**Output**: `validation.json`

## Phase 5: Final Preparation

### Stage 11: Add Section Breadcrumbs
**Purpose**: Build hierarchical navigation
**Code**: `extractor.core.processors.section_hierarchy`
**Input**: `merged_enhanced_sections.json`
**Output**: `final_sections.json`

### Stage 12: Generate Final Output
**Purpose**: Combine all results
**Code**: In pipeline script
**Output**: `final_output.json`

### Stage 13: Store Extraction Patterns
**Purpose**: Learn patterns for future extractions
**Code**: `claude -p` in `extract_pdf_pipeline.py:888-918`

## Phase 6: ArangoDB Insertion

### Stage 14: Transform to ArangoDB Format
**Purpose**: Convert to ArangoDB document structure
**Code**: `extractor.core.processors.arangodb_transformer` (if exists)
**Output**: Documents with proper `_key`, relationships

### Stage 15: Insert into ArangoDB
**Purpose**: Create documents and edges
**Code**: ArangoDB client code
**Collections**: `sections`, `relationships`

## Critical Issues & Solutions

### Problem 1: Garbage Sections (FRONT, END, etc.)
**Root Cause**: Table cells misidentified as section headers
**Solution**: Stage 6.5 - Validate sections with Claude
**Missing**: This stage is often skipped!

### Problem 2: Suspicious Headers Not Fixed
**Root Cause**: Stage 5.5 fixes blocks but Stage 6 uses original blocks
**Solution**: Ensure Stage 6 uses output from Stage 5.5c

### Problem 3: Unicode Directional Markers
**Root Cause**: PDFs contain RTL/LTR marks
**Solution**: Clean in post-processing

## Recommended Implementation Strategy

Given the complexity, I recommend:

1. **Keep the monolithic pipeline** but add missing Stage 6.5
2. **Add validation checkpoints** after each major phase
3. **Use working_usage() pattern** for testing each stage
4. **Add --stage flag** to run specific stages for debugging

The pipeline is sound in design but needs:
- Stage 6.5 (section validation with Claude)
- Better flow of fixed blocks from 5.5c to Stage 6
- Validation against gold standards at each phase