# Marker-PDF Architecture Analysis

## Overview

Marker-PDF is a sophisticated PDF processing framework that converts PDF documents into structured formats (Markdown, JSON, HTML) using a modular pipeline architecture. It employs computer vision, OCR, and optional LLM enhancement to extract and structure content from PDFs.

## Core Architecture

### 1. Main Entry Points

The system has two primary entry points:

- **`convert.py`**: Batch processing with multiprocessing support
  ```python
  convert_cli(in_folder, **kwargs)
  ```
  
- **`convert_single.py`**: Single PDF processing
  ```python
  convert_single_cli(fpath, **kwargs)
  ```

Both entry points follow the same pattern:
1. Create model dictionary (`create_model_dict()`)
2. Parse configuration via `ConfigParser`
3. Instantiate converter (default: `PdfConverter`)
4. Process the PDF
5. Save output via `save_output()`

### 2. Configuration System

The `ConfigParser` class manages all configuration:

```python
class ConfigParser:
    def __init__(self, cli_options: dict)
    
    # Key methods:
    def generate_config_dict() -> Dict  # Merges CLI options with defaults
    def get_converter_cls()             # Returns converter class (default: PdfConverter)
    def get_processors()                # Returns list of processor classes
    def get_renderer()                  # Returns renderer based on output format
    def get_llm_service()              # Returns LLM service if enabled
```

Configuration sources (in order of precedence):
1. CLI arguments
2. JSON config file (`--config_json`)
3. Environment variables (e.g., `GOOGLE_API_KEY`)
4. Default settings

### 3. PDF Converter Architecture

The `PdfConverter` is the main orchestrator:

```python
class PdfConverter(BaseConverter):
    def __init__(self, artifact_dict, processor_list, renderer, llm_service, config):
        # 1. Register custom block types
        # 2. Initialize processors
        # 3. Set up renderer
        # 4. Configure LLM service
    
    def __call__(self, filepath: str | io.BytesIO):
        # 1. Build document structure
        document = self.build_document(filepath)
        # 2. Run all processors
        for processor in self.processor_list:
            processor(document)
        # 3. Render output
        rendered = renderer(document)
        return rendered
```

### 4. Document Building Process

The document building follows this sequence:

```
PDF File → Provider → Builders → Document
```

#### 4.1 Provider Layer

The `PdfProvider` class handles PDF parsing:

```python
class PdfProvider(BaseProvider):
    def __init__(self, filepath: str, config=None):
        # 1. Open PDF with pypdfium2
        # 2. Extract text using pdftext library
        # 3. Build page lines and references
        # 4. Check for OCR requirements
```

Key responsibilities:
- Text extraction via `pdftext` library (multi-threaded)
- Page image rendering at different DPIs
- Font analysis and formatting detection
- Bad OCR detection
- Page validation (checking for text vs image-only pages)

#### 4.2 Builder Layer

Builders construct the document structure:

1. **DocumentBuilder**: Orchestrates the building process
   ```python
   def __call__(self, provider, layout_builder, line_builder, ocr_builder):
       document = self.build_document(provider)
       layout_builder(document, provider)  # Detect layout elements
       line_builder(document, provider)    # Build text lines
       ocr_builder(document, provider)     # Apply OCR if needed
       return document
   ```

2. **LayoutBuilder**: Detects document layout (columns, headers, etc.)
3. **LineBuilder**: Constructs text lines from spans
4. **OcrBuilder**: Applies OCR to image-based content
5. **StructureBuilder**: Builds hierarchical structure

### 5. Processing Pipeline

The default processor pipeline (in order):

```python
default_processors = (
    OrderProcessor,              # Establish reading order
    BlockRelabelProcessor,       # Relabel block types based on context
    LineMergeProcessor,         # Merge lines within blocks
    BlockquoteProcessor,        # Detect blockquotes
    CodeProcessor,              # Detect code blocks
    DocumentTOCProcessor,       # Extract table of contents
    EquationProcessor,          # Process equations
    FootnoteProcessor,          # Handle footnotes
    IgnoreTextProcessor,        # Mark text to ignore
    LineNumbersProcessor,       # Remove line numbers
    ListProcessor,              # Detect lists
    PageHeaderProcessor,        # Identify page headers
    SectionHeaderProcessor,     # Detect section headers
    TableProcessor,             # Process tables
    LLMTableProcessor,          # LLM enhancement for tables
    LLMTableMergeProcessor,     # Merge split tables
    LLMFormProcessor,           # Process forms
    TextProcessor,              # Handle text continuation
    LLMComplexRegionProcessor,  # Handle complex layouts
    LLMImageDescriptionProcessor, # Generate image descriptions
    LLMEquationProcessor,       # Enhance equation processing
    LLMHandwritingProcessor,    # Process handwriting
    LLMMathBlockProcessor,      # Process math blocks
    LLMSectionHeaderProcessor,  # Enhance section headers
    LLMPageCorrectionProcessor, # Page-level corrections
    ReferenceProcessor,         # Process references
    BlankPageProcessor,         # Handle blank pages
    DebugProcessor,             # Debug output
)
```

Each processor:
- Implements `__call__(self, document: Document)`
- Modifies the document in-place
- Can access and modify any block in the document

### 6. Document Schema

The document model is hierarchical:

```
Document
├── Page
│   ├── Block (Text, Table, Figure, etc.)
│   │   ├── Line
│   │   │   ├── Span
│   │   │   │   └── Char (optional)
```

Key schema classes:

```python
class Document:
    filepath: str
    pages: List[PageGroup]
    table_of_contents: List[TocItem]
    
class PageGroup(Block):
    page_id: int
    children: List[Block]  # All blocks on the page
    structure: List[BlockId]  # Reading order
    
class Block:
    id: BlockId
    polygon: PolygonBox  # Bounding box
    block_type: BlockTypes
    children: List[Block]  # Nested blocks
```

### 7. Rendering System

Renderers convert the processed document to output formats:

#### 7.1 JSON Renderer

```python
class JSONRenderer(BaseRenderer):
    def __call__(self, document: Document) -> JSONOutput:
        # 1. Render document structure
        # 2. Extract block HTML and images
        # 3. Generate metadata
        return JSONOutput(
            children=[...],  # Hierarchical block structure
            metadata={...}   # Page stats, TOC, etc.
        )
```

JSON output structure:
```json
{
  "children": [
    {
      "id": "page_0",
      "block_type": "Page",
      "children": [
        {
          "id": "text_0_1",
          "block_type": "Text",
          "html": "<p>Content</p>",
          "polygon": [[x1,y1], [x2,y2], ...],
          "bbox": [x, y, width, height],
          "section_hierarchy": {"1": "Introduction"}
        }
      ]
    }
  ],
  "metadata": {
    "table_of_contents": [...],
    "page_stats": [...]
  }
}
```

#### 7.2 Other Renderers

- **MarkdownRenderer**: Converts to Markdown with proper formatting
- **HTMLRenderer**: Generates semantic HTML
- **ChunkRenderer**: Creates chunks for RAG applications

### 8. LLM Integration

When `use_llm=True`, LLM services enhance processing:

```python
class GoogleGeminiService(BaseService):
    # Provides LLM capabilities to processors
```

LLM-enhanced processors can:
- Improve table structure recognition
- Generate image descriptions
- Correct OCR errors
- Enhance section header detection
- Process complex mathematical content

### 9. Output Management

The `save_output()` function handles all output formats:

```python
def save_output(rendered: BaseModel, output_dir: str, fname_base: str):
    # 1. Extract text, extension, and images from rendered output
    # 2. Save main content file (.md, .json, .html)
    # 3. Save metadata file (_meta.json)
    # 4. Save extracted images
```

### 10. Key Design Patterns

1. **Provider Pattern**: Abstracts PDF parsing from document building
2. **Builder Pattern**: Separates construction of complex document structure
3. **Pipeline Pattern**: Sequential processing through configurable processors
4. **Strategy Pattern**: Swappable renderers for different output formats
5. **Dependency Injection**: Models and services injected via `artifact_dict`

## Processing Flow Summary

```
1. PDF Input
   ↓
2. PdfProvider extracts text/images
   ↓
3. DocumentBuilder constructs initial structure
   ↓
4. LayoutBuilder detects layout elements
   ↓
5. LineBuilder builds text lines
   ↓
6. OcrBuilder applies OCR if needed
   ↓
7. StructureBuilder creates hierarchy
   ↓
8. Processors transform document
   ↓
9. Renderer produces output format
   ↓
10. Output saved to disk
```

## Key Features

1. **Multi-format Support**: PDF to Markdown, JSON, HTML, or chunks
2. **Configurable Pipeline**: Add/remove processors as needed
3. **LLM Enhancement**: Optional AI-powered improvements
4. **Parallel Processing**: Multi-worker support for batch conversion
5. **Extensible Architecture**: Easy to add new processors or renderers
6. **Robust Text Extraction**: Handles various PDF types and encodings
7. **Layout Understanding**: Preserves document structure and reading order
8. **Image Handling**: Extracts and processes embedded images
9. **Table Processing**: Advanced table detection and structure recovery
10. **Debug Support**: Comprehensive debugging options and outputs