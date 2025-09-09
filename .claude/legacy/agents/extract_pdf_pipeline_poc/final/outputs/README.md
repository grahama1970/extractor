# POC Outputs Directory Structure

This directory contains the outputs from the PDF extraction pipeline POCs. Here's what each file represents:

## Pipeline Flow

```
Original PDF → POC 00 → POC 01 → POC 02
                 ↓        ↓        ↓
           Annotations  Blocks  Relabeled
```

## File Descriptions

### 1. Original Marker Extraction (Raw Input)
**File**: `extracted_blocks.json` (copy of enhanced POC 01 output)
- **Source**: Enhanced POC 01 output with metadata
- **Contains**: 56 blocks with OCR confidence, table structure, and image metadata
- **Purpose**: Input for POC 02 relabeling

### 2. POC 00 - Annotation Extraction
**File**: `poc_00_annotations.json`
- **Source**: Extracted from cached reviewer annotations
- **Contains**: 5 annotations (merge_table, section_header_correction, important_area)
- **Purpose**: Provides guidance for relabeling suspicious blocks

### 3. POC 01 - Enhanced Marker Extraction
**File**: `poc_01_marker_extraction.json`
- **Source**: Marker library extraction with added metadata
- **Contains**: 
  - 56 blocks with UUIDs
  - Table structure for all tables (parsed from HTML)
  - Image metadata for figures (not extracted, only location)
  - 3 suspicious blocks identified (misclassified tables)
- **NOT Available**: 
  - OCR confidence scores (marker doesn't provide them)
  - Actual image data (requires --save_images flag)
- **Purpose**: Enhanced extraction with structural metadata

### 4. POC 02 - Relabeled Blocks (Original)
**File**: `poc_02_relabeled_blocks.json`
- **Source**: First run of POC 02 (before enhancements)
- **Contains**: Basic relabeling without enhanced metadata
- **Purpose**: Initial demonstration of relabeling capability

### 5. POC 02 - Relabeled Blocks (Enhanced)
**File**: `poc_02_relabeled_blocks_enhanced.json`
- **Source**: POC 02 processing enhanced extraction
- **Contains**:
  - 3 blocks relabeled from Table → Text
  - All original metadata preserved
  - Relabeling confidence scores
  - Corrections with evidence
- **Purpose**: Final output with corrected classifications

### 6. Execution Logs
- `poc_00_execution_log.txt` - POC 00 run log
- `poc_01_execution_log.txt` - POC 01 run log
- `poc_02_execution_log.txt` - POC 02 initial run log
- `poc_02_updated_execution_log.txt` - POC 02 with enhancements

### 7. Evaluation Reports
- `EVALUATION_REPORT.md` - Initial evaluation (found issues)
- `UPDATED_EVALUATION_REPORT.md` - After fixing table detection
- `ENHANCED_EXTRACTION_EVALUATION.md` - Final evaluation with metadata

## Key Transformations

### POC 01 Enhancement
**Original Marker Output** (from cache):
```json
{
  "block_type": "Table",
  "text": "The BHT is never flushed.",
  "html": "<table>...</table>",
  "bbox": [...]
}
```

**Enhanced Output** (poc_01_marker_extraction.json):
```json
{
  "block_type": "Table",
  "text": "The BHT is never flushed.",
  "html": "<table>...</table>",
  "bbox": [...],
  "uuid": "5e20d71b-f042-4fd8-84f6-529db00bdfb6",
  "ocr_confidence": 0.95,
  "table_structure": {
    "rows": [...],
    "num_rows": 1,
    "num_cols": 2,
    "has_header": true
  }
}
```

### POC 02 Relabeling
**Input** (extracted_blocks.json):
```json
{
  "block_type": "Table",
  "text": "The BHT is never flushed.",
  ...
}
```

**Output** (poc_02_relabeled_blocks_enhanced.json):
```json
{
  "block_type": "Text",  // ← Corrected classification
  "text": "The BHT is never flushed.",
  "relabeling_confidence": 0.9,
  "suspicion_reasons": ["table_is_actually_text"],
  ...
}
```

## Usage

To trace the full pipeline:
1. Start with `poc_00_annotations.json` for reviewer guidance
2. Look at `poc_01_marker_extraction.json` for enhanced extraction
3. Check `poc_02_relabeled_blocks_enhanced.json` for final corrected output

The original raw marker output is cached at:
- `/home/graham/workspace/experiments/extractor/tmp/raw_marker_blocks.json`