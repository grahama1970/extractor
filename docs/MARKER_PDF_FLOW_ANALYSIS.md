# Marker-PDF Processing Flow Analysis

## Overview
The marker-pdf codebase processes PDFs through a sophisticated pipeline that combines computer vision models (Surya) with PDF parsing (pypdfium2) to extract structured content.

## Core Processing Flow

### 1. PDF Input & Provider Layer
- **Component**: `PdfProvider` (src/extractor/core/providers/pdf.py)
- **Library**: pypdfium2
- **Functions**:
  - Opens PDF document using `pdfium.PdfDocument(filepath)`
  - Extracts text using pdftext library with `dictionary_output()`
  - Renders pages to images at different DPIs (96 for layout, 192 for OCR)
  - Extracts character-level bounding boxes and font information
  - Performs initial text quality checks to determine if OCR is needed

### 2. Document Building
- **Component**: `DocumentBuilder` (src/extractor/core/builders/document.py)
- **Process**:
  ```python
  document = DocumentBuilder(config)(provider, layout_builder, line_builder, ocr_builder)
  ```
  - Creates page groups with low-res and high-res images
  - Initializes document structure with pages and metadata

### 3. Layout Detection (Surya)
- **Component**: `LayoutBuilder` (src/extractor/core/builders/layout.py)
- **Model**: Surya layout detection model
- **Process**:
  - Takes page images and runs through `LayoutPredictor`
  - Detects layout regions (text, figure, table, equation, etc.)
  - Returns `LayoutResult` with bounding boxes and labels
  - Each bbox has confidence scores (`top_k`) for different block types
  - Rescales layout bboxes to match provider page coordinates

### 4. Line Detection & OCR
- **Component**: `LineBuilder` (src/extractor/core/builders/line.py)
- **Models**: 
  - Surya text detection model
  - Surya OCR recognition model
  - OCR error detection model
- **Process**:
  - Detects text lines using detection model
  - Checks if provider text extraction is good quality
  - If OCR needed, runs Surya recognition model on detected lines
  - Merges provider lines with OCR results

### 5. Bbox Intersection Logic
- **Core Function**: `matrix_intersection_area()` (src/extractor/core/util.py)
- **Purpose**: Calculate overlap between bounding boxes
- **Implementation**:
  ```python
  # Vectorized numpy calculation for N×M bbox pairs
  min_x = np.maximum(boxes1[..., 0], boxes2[..., 0])
  min_y = np.maximum(boxes1[..., 1], boxes2[..., 1])
  max_x = np.minimum(boxes1[..., 2], boxes2[..., 2])
  max_y = np.minimum(boxes1[..., 3], boxes2[..., 3])
  width = np.maximum(0, max_x - min_x)
  height = np.maximum(0, max_y - min_y)
  return width * height
  ```
- **Used for**:
  - Matching layout blocks with provider text lines
  - Determining if OCR lines overlap with existing text
  - Merging adjacent lines
  - Table cell detection
  - Inline math detection

### 6. Block Processing Pipeline
- **Sequential Processors**: Applied in order defined in `PdfConverter.default_processors`
- **Key Processors**:
  - `OrderProcessor`: Establishes reading order
  - `LineMergeProcessor`: Merges adjacent lines based on proximity
  - `TableProcessor`: Extracts tables (with Camelot fallback)
  - `SectionHeaderProcessor`: Identifies headers
  - `TextProcessor`: Final text extraction and formatting
  - LLM processors for enhanced extraction (if enabled)

### 7. Structure Building
- **Component**: `StructureBuilder`
- **Creates hierarchical relationships**:
  - Document → Pages → Blocks → Lines → Spans → Characters
  - Parent-child relationships maintained throughout

### 8. Rendering
- **Component**: `MarkdownRenderer` (default)
- **Output formats**: Markdown, JSON, HTML
- **Preserves**:
  - Section hierarchy
  - Tables with proper formatting
  - Code blocks
  - Equations
  - Lists and footnotes

## Key Data Structures

### PolygonBox
- Represents bounding boxes as 4-point polygons
- Methods:
  - `intersection_area()`: Calculate overlap area
  - `intersection_pct()`: Overlap as percentage of box area
  - `rescale()`: Convert between coordinate systems
  - `merge()`: Combine multiple boxes

### Block Hierarchy
```
Document
  └── PageGroup
      ├── LayoutBlock (from Surya)
      ├── Line (from detection/provider)
      │   └── Span (text with formatting)
      │       └── Char (individual characters)
      └── SpecialBlocks (Table, Figure, Equation, etc.)
```

## Performance Optimizations
- Batch processing for Surya models
- Vectorized bbox calculations using numpy
- Caching of model results
- Configurable batch sizes based on device (CUDA/CPU)
- Memory-aware processing for large PDFs

## Error Handling & Fallbacks
- Falls back to PyMuPDF if Surya fails
- OCR quality detection with thresholds
- Camelot fallback for complex tables
- Graceful degradation when models unavailable