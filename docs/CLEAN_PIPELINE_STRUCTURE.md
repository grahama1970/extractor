# Clean PDF Extraction Pipeline Structure

## Overview

The PDF extraction pipeline has been reorganized into 4 clean, logical steps:

## Pipeline Steps

### **Step 01: Extract Annotations** (`poc_01_extract_annotations.py`)
- **Purpose**: Learn from human annotations to improve future extractions
- **Input**: PDF files with human annotations
- **Process**: 
  - Extracts annotations using PyMuPDF
  - Creates visual snapshots (40% taller for context)
  - Analyzes with Claude to understand patterns
  - Stores patterns in ArangoDB
- **Output**: Learned patterns and annotation analyses
- **Key Point**: This step runs FIRST to inform the rest of the pipeline

### **Step 02: Extract Raw Content** (`poc_02_marker_extraction.py`)
- **Purpose**: Extract all content from PDFs
- **Input**: Any PDF file
- **Process**:
  - Uses Marker library (which internally uses Surya)
  - Extracts text, tables, images, and layout
  - Adds UUIDs for tracking blocks
  - Identifies suspicious/misclassified content
- **Output**: Raw blocks with metadata
- **Note**: Surya does NOT provide confidence scores

### **Step 03: Clean & Apply Patterns** (`poc_03_clean_and_enhance.py`)
- **Purpose**: Clean and enhance extracted content
- **Input**: Raw blocks from Step 02
- **Process**:
  - Cleans OCR errors and formatting issues
  - Searches ArangoDB for learned patterns from Step 01
  - Re-classifies suspicious blocks (e.g., table cells as headers)
  - Builds hierarchical document structure
  - Uses Claude for visual validation when needed
- **Output**: Cleaned, structured content with corrections

### **Step 04: Export to ArangoDB** (`poc_04_export_arangodb.py`)
- **Purpose**: Store final results in ArangoDB
- **Input**: Enhanced content from Step 03
- **Process**:
  - Creates document records
  - Exports blocks with full metadata
  - Creates graph relationships (document → sections → blocks)
  - Links to learned patterns
  - Maintains provenance chain
- **Output**: Complete document graph in ArangoDB

## Key Improvements

1. **Knowledge First**: Step 01 learns from annotations before processing
2. **No Redundancy**: Each step has a clear, unique purpose
3. **No Confidence Scores**: Removed quality assessment based on confidence (Surya doesn't provide them)
4. **Direct Storage**: Results go directly to ArangoDB, not returned to parent
5. **Clean Separation**: Each POC file is self-contained with CLI support

## Deleted Files

The following redundant files should be removed:
- `poc_00_extract_annotations.py` (renamed to poc_01)
- `poc_01_5_selective_camelot.py` (functionality in poc_03 if needed)
- `poc_03_ocrmypdf_confidence.py` (no confidence scores available)
- `poc_04_quality_assessment.py` (no confidence scores to assess)
- `poc_05_complete_pipeline.py` (redundant orchestrator)
- `poc_05_pipeline_with_validation.py` (redundant orchestrator)
- `poc_06_pipeline_gold_standard_format.py` (formatting now in poc_04)
- `poc_07_final_secure_pipeline.py` (security built into each step)
- `poc_08_claude_code_integration.py` (integrated throughout)
- `poc_08_working_claude_calls.py` (redundant)

## Usage Examples

### Full Pipeline Execution
```bash
# Step 1: Learn from annotations (if available)
python poc_01_extract_annotations.py

# Step 2: Extract content
python poc_02_marker_extraction.py extract document.pdf

# Step 3: Clean and enhance
python poc_03_clean_and_enhance.py clean outputs/poc_02_marker_extraction.json --pdf-path document.pdf

# Step 4: Export to ArangoDB
python poc_04_export_arangodb.py export outputs/poc_03_clean_and_enhance.json document.pdf
```

### Testing Individual Steps
```bash
# Test each step's functionality
python poc_01_extract_annotations.py debug
python poc_02_marker_extraction.py debug
python poc_03_clean_and_enhance.py debug
python poc_04_export_arangodb.py debug
```

## Architecture Benefits

1. **Modular**: Each step can be run independently
2. **Testable**: Each POC has working_usage() and debug_function()
3. **Observable**: Progress stored in ArangoDB in real-time
4. **Learnable**: System improves from human annotations
5. **Maintainable**: Clear separation of concerns

## Future Enhancements

- Add embedding generation in Step 03 or 04
- Implement more sophisticated pattern learning
- Add support for multi-language documents
- Integrate with downstream NLP pipelines