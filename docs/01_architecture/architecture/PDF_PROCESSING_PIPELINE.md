# PDF Processing Pipeline Architecture

## Overview

The Marker PDF processing pipeline transforms PDF documents into structured markdown through a series of specialized processors. This document details the complete pipeline architecture.

## Pipeline Stages

### 1. PDF Loading and Parsing
- **Component**: `PdfProvider`
- **Purpose**: Extract raw content from PDF files
- **Input**: PDF file path
- **Output**: PyPDF2 document object with pages

### 2. Layout Detection  
- **Component**: `LayoutBuilder` with Surya models
- **Purpose**: Identify document regions and structure
- **Models**: 
  - `surya_det`: Layout detection
  - `surya_layout`: Element classification
- **Output**: Layout elements with bounding boxes

### 3. OCR Processing
- **Component**: `OcrBuilder` with Surya recognition
- **Purpose**: Extract text from images and scanned content
- **Model**: `surya_rec` 
- **Output**: OCR text with confidence scores

### 4. Block Construction
- **Component**: `DocumentBuilder`
- **Purpose**: Create document block hierarchy
- **Process**:
  1. Group layout elements into blocks
  2. Create line and span structures
  3. Establish parent-child relationships
- **Output**: Hierarchical block structure

### 5. Block Processing
Sequential processors that enhance and transform blocks:

#### Text Processing
- **LineProcessor**: Merges adjacent lines
- **TextProcessor**: Cleans and formats text

#### Structure Processing  
- **SectionHeaderProcessor**: Identifies section headers
- **ListProcessor**: Detects and formats lists
- **FootnoteProcessor**: Extracts footnotes

#### Table Processing
- **TableProcessor**: Primary table extraction
- **EnhancedTableProcessor**: Camelot fallback
- **TableOptimizer**: Improves table quality

#### Code Processing
- **CodeProcessor**: Detects code blocks
- **EquationProcessor**: Handles math equations

#### Enhanced Features
- **ImageDescriptionProcessor**: AI-powered image captions
- **SectionSummarizer**: Creates section summaries
- **HierarchyBuilder**: Builds section hierarchy

### 6. Document Assembly
- **Component**: `Document` class
- **Purpose**: Assemble final document structure
- **Features**:
  - Section hierarchy with breadcrumbs
  - Table of contents generation
  - Metadata preservation

### 7. Rendering
- **Components**: Various renderers
- **Options**:
  - Markdown (primary)
  - JSON (structured data)
  - HTML (web display)
  - Hierarchical JSON (enhanced)

## Data Flow

```
PDF File
    ↓
PdfProvider (extraction)
    ↓
LayoutBuilder (detection)
    ↓
OcrBuilder (recognition)
    ↓
DocumentBuilder (structure)
    ↓
Block Processors (enhancement)
    ↓
Document Assembly (organization)
    ↓
Renderer (output)
    ↓
Markdown/JSON/HTML
```

## Key Technologies

### Surya Models
- Pre-trained vision models for document analysis
- Three model types:
  - Detection: Layout regions
  - Layout: Element classification
  - Recognition: OCR

### LiteLLM Integration
- Unified interface for multiple LLM providers
- Used for:
  - Image descriptions
  - Section summaries
  - Table understanding

### Camelot
- Fallback table extraction library
- Handles complex table structures
- PDF-specific algorithms

## Performance Optimization

### Batch Processing
- Process multiple pages simultaneously
- Configurable batch size
- Memory-aware batching

### Caching
- Model caching for repeated use
- Result caching for common operations
- Table extraction cache

### Parallel Processing
- Async image description
- Parallel block processing
- Multi-threaded rendering

## Configuration

Key configuration options:
```python
ParserConfig(
    model_list=["surya_det", "surya_rec"],
    batch_multiplier=2,
    device="cuda",
    llm_provider="litellm",
    table_extraction=True,
    image_description=True
)
```

## Error Handling

- Graceful degradation for failures
- Fallback strategies for each component
- Comprehensive error logging
- Recovery mechanisms

## Extension Points

1. **Custom Processors**: Add new block processors
2. **Model Plugins**: Integrate alternative ML models  
3. **Renderer Extensions**: Create custom output formats
4. **Provider Additions**: Support new file types