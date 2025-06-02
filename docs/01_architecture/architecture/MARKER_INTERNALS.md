# Marker Internals: Key Functions and Operations

This document provides a detailed overview of the key functions and operations in the Marker project, including both the core functionality and the enhancements made in this fork.

## Table of Contents
1. [PDF to Marker Block Conversion](#pdf-to-marker-block-conversion)
2. [PDF Blocks to Text Conversion](#pdf-blocks-to-text-conversion)
3. [Section Hierarchy and Metadata](#section-hierarchy-and-metadata)
4. [Surya Model Integration](#surya-model-integration)
5. [LLM Usage in Marker](#llm-usage-in-marker)
6. [Fork Enhancements](#fork-enhancements)
7. [PDF Block Conversion Timeline](#pdf-block-conversion-timeline)
8. [Additional Fork Features](#additional-fork-features)
9. [LLM Image Description](#llm-image-description)
10. [Enhanced Camelot Integration](#enhanced-camelot-integration)
11. [Image Processing Pipeline](#image-processing-pipeline)
12. [Table Processing Enhancements](#table-processing-enhancements)
13. [Utility Enhancements](#utility-enhancements)
14. [Renderer Additions](#renderer-additions)
15. [Performance Optimizations](#performance-optimizations)
16. [Configuration System](#configuration-system)
17. [Testing Infrastructure](#testing-infrastructure)
18. [CLI Enhancements](#cli-enhancements)
19. [Error Handling and Logging](#error-handling-and-logging)

---

## 1. PDF to Marker Block Conversion

The PDF to Marker block conversion happens through a series of builders that process the PDF in stages.

### Main Conversion Pipeline
**File**: `marker/converters/pdf.py`
**Function**: `PdfConverter.build_document()` (lines 124-153)

The conversion follows this sequence:

1. **Provider Creation**: 
   ```python
   # marker/converters/pdf.py:128-129
   provider = provider_from_filepath(self.override_map, self.parallel_workers)
   provider.set_config(config)
   ```

2. **Document Building**:
   ```python
   # marker/converters/pdf.py:131-135
   document_builder = DocumentBuilder(config)
   document = document_builder(
       provider, layout_builder, line_builder, ocr_builder
   )
   ```

3. **Layout Detection**:
   ```python
   # marker/converters/pdf.py:132
   layout_builder = LayoutBuilder(artifact_dict["detection_model"], config)
   ```

4. **Structure Building**:
   ```python
   # marker/converters/pdf.py:138
   document = StructureBuilder(config)(document)
   ```

### Document Builder
**File**: `marker/builders/document.py`
**Function**: `DocumentBuilder.__call__()` (lines 31-37)
**Function**: `DocumentBuilder.build_document()` (lines 39-58)

```python
def __call__(self, provider: PdfProvider, layout_builder: LayoutBuilder, 
             line_builder: LineBuilder, ocr_builder: OcrBuilder):
    document = self.build_document(provider)
    layout_builder(document, provider)
    line_builder(document, provider)
    if not self.disable_ocr:
        ocr_builder(document, provider)
    return document

def build_document(self, provider: PdfProvider):
    PageGroupClass: PageGroup = get_block_class(BlockTypes.Page)
    lowres_images = provider.get_images(provider.page_range, self.lowres_image_dpi)
    highres_images = provider.get_images(provider.page_range, self.highres_image_dpi)
    initial_pages = [
        PageGroupClass(
            page_id=p,
            lowres_image=lowres_images[i],
            highres_image=highres_images[i],
            polygon=provider.get_page_bbox(p),
            refs=provider.get_page_refs(p)
        ) for i, p in enumerate(provider.page_range)
    ]
    return Document(filepath=provider.filepath, pages=initial_pages)
```

### Layout Builder
**File**: `marker/builders/layout.py`
**Function**: `LayoutBuilder.__call__()` (lines 39-45)
**Function**: `LayoutBuilder.surya_layout()` (lines 64-89)

Uses Surya's layout detection model to identify different block types:

```python
def __call__(self, document: Document, provider: PdfProvider):
    if self.force_layout_block is not None:
        # Assign the full content of every page to a single layout type
        layout_results = self.forced_layout(document.pages)
    else:
        layout_results = self.surya_layout(document.pages)
    self.add_blocks_to_pages(document.pages, layout_results)

def surya_layout(self, pages: List[PageGroup]) -> List[LayoutResult]:
    page_images = [p.lowres_image for p in pages]
    
    layout_predictions = self.layout_model.batch_prediction(
        page_images,
        batch_size=self.get_batch_size(),
        disable_tqdm=self.disable_tqdm
    )
    return layout_predictions
```

**Function**: `LayoutBuilder.add_blocks_to_pages()` (lines 91-121)
```python
def add_blocks_to_pages(self, pages: List[PageGroup], layout_results: List[LayoutResult]):
    for page, layout_result in zip(pages, layout_results):
        bbox_list = [b.bbox for b in layout_result.bboxes]
        block_type_names = [b.label for b in layout_result.bboxes]
        
        for bbox, block_type_name in zip(bbox_list, block_type_names):
            block_type = BlockTypes[block_type_name]
            BlockClass = get_block_class(block_type)
            block = BlockClass(
                polygon=PolygonBox.from_bbox(bbox),
                page_id=page.page_id
            )
            page.add_child(block)
```

---

## 2. PDF Blocks to Text Conversion

Text extraction from PDF blocks happens through a hierarchical process using the `raw_text()` method.

### Base Text Extraction Method
**File**: `marker/schema/blocks/base.py`
**Function**: `Block.raw_text()` (lines 168-189)

```python
def raw_text(self, document: Document) -> str:
    from marker.schema.text.line import Line
    from marker.schema.text.span import Span
    from marker.schema.blocks.tablecell import TableCell

    # For leaf blocks (Span, TableCell)
    if self.structure is None:
        if isinstance(self, (Span, TableCell)):
            return self.text
        else:
            return ""

    # For container blocks - recursively get text from children
    text = ""
    for block_id in self.structure:
        block = document.get_block(block_id)
        if block:
            text += block.raw_text(document)
            if isinstance(block, Line) and not text.endswith("\n"):
                text += "\n"
    return text
```

### Block Hierarchy
```
Document
└── Page
    └── Block (Text, SectionHeader, Table, etc.)
        └── Line
            └── Span (contains actual text)
```

### Text Storage
- **Span blocks** (`marker/schema/text/span.py`): Contains the actual text in `text` property
- **Line blocks** (`marker/schema/text/line.py`): Aggregates spans
- **Higher blocks**: Aggregate lines and other blocks

---

## 3. Section Hierarchy and Metadata

Section hierarchy and metadata are added through processors that run after the initial document structure is built.

### Section Header Processor
**File**: `marker/processors/sectionheader.py`
**Function**: `SectionHeaderProcessor.__call__()` (lines 38-98)

```python
def __call__(self, document: Document):
    line_heights: Dict[int, float] = {}
    for page in document.pages:
        # Iterate children to grab all section headers
        for block in page.children:
            if block.block_type not in self.block_types:
                continue
            if block.structure is not None:
                line_heights[block.id] = block.line_height(document)
            else:
                line_heights[block.id] = 0
                block.ignore_for_output = True
    
    # Use K-means clustering to find heading levels
    self.heading_ranges = self.get_heading_levels(line_heights)
    
    # Assign heading levels to each section header
    for page in document.pages:
        for block in page.contained_blocks(document, self.block_types):
            heading_level = self.get_heading_level(
                block.line_height(document), 
                prev_heading_gap
            )
            block.heading_level = heading_level
```

### Hierarchy Builder (Fork Enhancement)
**File**: `marker/processors/enhanced/hierarchy_builder.py`
**Function**: `HierarchyBuilder.__call__()` (lines 31-48)
**Function**: `HierarchyBuilder._build_hierarchy()` (lines 50-98)

```python
def __call__(self, document: Document) -> Document:
    """Build hierarchical structure and attach to document"""
    logger.info("Building hierarchical document structure")
    
    # Create hierarchical document
    hierarchical_doc = self._build_hierarchy(document)
    
    # Attach to original document metadata
    if not hasattr(document, 'metadata') or document.metadata is None:
        document.metadata = {}
    
    document.metadata['hierarchical_structure'] = hierarchical_doc
    return document

def _build_hierarchy(self, document: Document) -> HierarchicalDocument:
    # Create metadata structures
    file_metadata = FileMetadata(
        filepath=Path(document.filepath),
        file_size=os.path.getsize(document.filepath),
        file_hash=self._compute_file_hash(document.filepath)
    )
    
    # Create hierarchical document
    hierarchical_doc = HierarchicalDocument(
        file_metadata=file_metadata,
        processing_metadata=processing_metadata,
        document_metadata=doc_metadata
    )
    
    # Process pages and build sections
    for page in document.pages:
        self._process_page_blocks(
            page, hierarchical_doc, current_section, section_stack, document
        )
```

### Section Hash Generation
**File**: `marker/schema/blocks/sectionheader.py`
**Function**: `SectionHeader.compute_section_hash()` (lines 17-34)

```python
def compute_section_hash(self, document):
    """Compute a hash of the section content."""
    # Start with the section title
    content = self.raw_text(document) if document else self.raw_text(None)

    if document:
        # Find content within this section
        section_blocks = self.get_section_content(document)
        for block in section_blocks:
            content += block.raw_text(document)

    # Generate a hash of the content
    hash_value = hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    return hash_value
```

### Breadcrumb Building
**File**: `marker/schema/blocks/sectionheader.py`
**Function**: `SectionHeader._build_breadcrumb_array()` (lines 70-96)

```python
def _build_breadcrumb_array(self, section_hierarchy):
    """Build a breadcrumb array with [parent, ..., this section]."""
    breadcrumb = []
    # Add all parent sections in order
    for level in sorted(section_hierarchy.keys()):
        if level < self.heading_level:
            parent = section_hierarchy[level]
            breadcrumb.append({
                "title": parent.get("title", ""),
                "hash": parent.get("hash", ""),
                "level": level
            })
    
    # Add this section
    breadcrumb.append({
        "title": self.raw_text(None).strip(),
        "hash": self.section_hash,
        "level": self.heading_level
    })
    return breadcrumb
```

### Metadata Addition Points
1. **During Layout Detection**: Basic block metadata (type, position, bbox)
2. **During Processing**: 
   - Section levels (SectionHeaderProcessor)
   - Section hashes and breadcrumbs (fork enhancement)
   - Content summaries (SectionSummarizer)
3. **During Hierarchy Building**: Full hierarchical structure
4. **During Rendering**: Final output metadata

---

## 4. Surya Model Integration

Surya models are used for layout detection, OCR, and table recognition.

### Layout Detection
**File**: `marker/builders/layout.py`
**Import**: `from surya.layout import LayoutPredictor` (line 3)
**Function**: `LayoutBuilder.surya_layout()` (lines 64-89)

```python
def surya_layout(self, pages: List[PageGroup]) -> List[LayoutResult]:
    # Extract low-resolution images from pages
    page_images = [p.lowres_image for p in pages if p.lowres_image is not None]
    
    # Add any missing images
    for p_idx, p in enumerate(pages):
        if p.lowres_image is None:
            page_images.insert(p_idx, self.default_image())
    
    # Run Surya layout detection using the layout predictor
    layout_predictions = self.layout_model.batch_prediction(
        page_images,
        batch_size=self.get_batch_size(),
        disable_tqdm=self.disable_tqdm
    )
    return layout_predictions
```

The LayoutPredictor from Surya:
- Detects regions like Text, Title, Figure, Table, List, etc.
- Returns bounding boxes with confidence scores
- Identifies document structure elements

### OCR with Surya
**File**: `marker/builders/ocr.py`
**Import**: `from surya.ocr import OCRPredictor` (line 11)
**Function**: `OcrBuilder.__call__()` (lines 44-49)
**Function**: `OcrBuilder.ocr_blocks()` (lines 70-124)

```python
def __call__(self, document: Document, provider: PdfProvider):
    ocr_blocks = self.ocr_blocks(document, provider)
    self.surya_ocr(document, ocr_blocks)

def ocr_blocks(self, document: Document, provider: PdfProvider):
    # Collect blocks that need OCR
    blocks_to_ocr = []
    for page in document.pages:
        for block in page.contained_blocks(document, self.block_types):
            bbox = block.polygon.bbox
            
            # Check if block has text from provider
            provider_text = provider.font_flags_for_bbox(
                page.page_id, bbox, self.font_flags
            )
            
            if not provider_text or self.should_ocr_block(block):
                blocks_to_ocr.append(block)
    
    return blocks_to_ocr

def surya_ocr(self, document: Document, ocr_blocks: List[Block]):
    # Prepare images for OCR
    images = []
    for block in ocr_blocks:
        image = block.get_image(document, highres=True)
        images.append(image)
    
    # Run OCR
    ocr_result = self.recognition_model.batch_prediction(
        images,
        self.detection_model,
        batch_size=self.batch_size,
        disable_tqdm=self.disable_tqdm
    )
    
    # Update blocks with OCR results
    for block, result in zip(ocr_blocks, ocr_result):
        block.text = result.text
        block.confidence = result.confidence
```

### Table Recognition
**File**: `marker/processors/table.py`
**Import**: `from surya.table_rec import TableRecPredictor` (line 17)
**Function**: `TableProcessor.__call__()` (lines 39-41)
**Function**: `TableProcessor.get_table_surya()` (lines 89-125)

```python
def __call__(self, document: Document):
    for page in document.pages:
        for block in page.contained_blocks(document, self.block_types):
            self.format_tables(document, block)

def get_table_surya(self, document: Document, table_block: BaseTable):
    table_image = table_block.get_image(document, highres=True)
    
    # Run Surya table recognition
    table_result = self.table_model.batch_prediction(
        [table_image],
        batch_size=self.get_batch_size(),
        disable_tqdm=self.disable_tqdm
    )
    
    # Extract structure
    rows = defaultdict(dict)
    cells = table_result[0].cells if table_result else []
    
    for cell in cells:
        col_idx = cell.col_idx
        row_idx = cell.row_idx
        
        spans = self.extract_cell_text(document, cell.bbox)
        
        if spans:
            cell_text = " ".join(span.text for span in spans)
            rows[row_idx][col_idx] = cell_text
    
    return rows
```

---

## 5. LLM Usage in Marker

LLMs are used optionally in Marker to enhance accuracy for specific tasks. The project is NOT completely LLM-based - LLMs are used selectively for quality improvement.

### LLM Service Architecture
**File**: `marker/services/litellm.py` (Fork Enhancement)
**Function**: `LiteLLMService.generate()` (lines 34-67)

```python
class LiteLLMService(BaseService):
    def generate(self, prompt: str, **kwargs) -> str:
        response = litellm.completion(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            **kwargs
        )
        return response.choices[0].message.content
```

### LLM Processors
1. **Table Processing**:
   - **File**: `marker/processors/llm/llm_table.py`
   - **Purpose**: Improve table detection and structure

2. **Equation Processing**:
   - **File**: `marker/processors/llm/llm_equation.py`
   - **Purpose**: Convert complex equations to LaTeX

3. **Form Processing**:
   - **File**: `marker/processors/llm/llm_form.py`
   - **Purpose**: Extract form fields and values

4. **Image Description**:
   - **File**: `marker/processors/llm/llm_image_description.py`
   - **Purpose**: Generate alt text for images

5. **Section Summarization** (Fork Enhancement):
   - **File**: `marker/processors/enhanced/summarizer.py`
   - **Purpose**: Create summaries for sections

### When LLMs are Used
- Only when `--use_llm` flag is passed
- For specific complex tasks where rule-based approaches struggle
- Always as an enhancement, never as the primary extraction method

---

## PDF Block Conversion Timeline

Understanding when each type of conversion happens:

### 1. Initial Document Creation (Provider Stage)
- **PDF Loading**: `PdfProvider` loads the PDF using PyPdfium2
- **Page Images**: Created at two resolutions (96 DPI for layout, 192 DPI for OCR)
- **Text Extraction**: Initial text extraction from PDF if available

### 2. Layout Detection (Builder Stage)
- **Timing**: Immediately after document creation
- **Surya Model**: Detects regions (Text, Title, Figure, Table, etc.)
- **Output**: Creates block objects with bounding boxes

### 3. Line Detection (Builder Stage)
- **Timing**: After layout detection
- **Purpose**: Identifies individual lines within text blocks
- **Method**: Geometric analysis and text positioning

### 4. OCR Processing (Builder Stage)
- **Timing**: After line detection, only if needed
- **Condition**: When PDF text is missing or poor quality
- **Surya OCR**: Performs optical character recognition

### 5. Block Processing (Processor Stage)
- **Timing**: After all builders complete
- **Order**: Processors run in sequence defined in `default_processors`
- **Examples**:
  - `SectionHeaderProcessor`: Identifies headers, assigns levels
  - `TableProcessor`: Processes table structure
  - `TextProcessor`: Formats text blocks

### 6. LLM Enhancement (Optional)
- **Timing**: During processor stage if `--use_llm` flag
- **Selective**: Only for specific processors (tables, equations, forms)

### 7. Hierarchy Building (Fork Enhancement)
- **Timing**: After all standard processors
- **Purpose**: Creates nested structure from flat blocks

### 8. Summarization (Fork Enhancement)
- **Timing**: After hierarchy building
- **Condition**: When `--add-summaries` flag is used

### 9. Rendering (Final Stage)
- **Timing**: After all processing complete
- **Options**: Markdown, HTML, JSON, ArangoDB JSON

---

## 6. Fork Enhancements

This fork adds several key enhancements to the original Marker:

### 1. Section Breadcrumbs
**Purpose**: Enable hierarchical navigation for ArangoDB integration

**Implementation**:
```python
# marker/schema/blocks/sectionheader.py:58-71
class SectionHeader(Block):
    # Added fields
    section_hierarchy_titles: List[str] = []
    section_hierarchy_hashes: List[str] = []
    
    def assign_section_hierarchy(self, parent_hierarchy):
        # Build breadcrumb trail
        self.section_hierarchy_titles = parent_hierarchy + [self.title]
        self.section_hierarchy_hashes = generate_hashes(self.section_hierarchy_titles)
```

### 2. LiteLLM Integration
**Purpose**: Unified interface for multiple LLM providers

**File**: `marker/services/litellm.py`
```python
class LiteLLMService(BaseService):
    supported_models = [
        'openai/*',
        'anthropic/*',
        'gemini/*',
        'vertex_ai/*'
    ]
    
    def __init__(self, model_name='gemini-2.0-flash-exp', **kwargs):
        self.model_name = model_name
        self.temperature = kwargs.get('temperature', 0.3)
```

### 3. Document Hierarchy
**Purpose**: Transform flat structure to hierarchical with sections as containers

**File**: `marker/processors/enhanced/hierarchy_builder.py`
```python
def build_hierarchy(self, document: Document) -> HierarchicalDocument:
    sections = []
    current_section = None
    
    for block in document.blocks:
        if isinstance(block, SectionHeader):
            current_section = Section(
                header=block,
                content_blocks=[],
                subsections=[]
            )
            sections.append(current_section)
        else:
            current_section.content_blocks.append(block)
    
    return HierarchicalDocument(sections=sections)
```

### 4. Section Summarization
**Purpose**: Automatic LLM-generated summaries for sections

**File**: `marker/processors/enhanced/summarizer.py`
```python
def summarize_section(self, section: Section) -> str:
    content = self.extract_section_content(section)
    
    response = litellm.completion(
        model=self.model_name,
        messages=[{
            "role": "user", 
            "content": f"Summarize this section:\n{content}"
        }],
        max_tokens=200
    )
    
    return response.choices[0].message.content
```

### 5. ArangoDB Renderer
**Purpose**: Export documents in ArangoDB-compatible format

**File**: `marker/renderers/arangodb_json.py`
```python
def render(self, document: Document) -> dict:
    return {
        "_key": document.doc_id,
        "type": "document",
        "sections": self.render_sections(document),
        "metadata": self.render_metadata(document)
    }
```

### Summary of Fork Changes
1. **Added Features**:
   - Section breadcrumbs with hashes
   - LiteLLM service for flexible LLM usage
   - Hierarchical document structure
   - Section summarization
   - ArangoDB export

2. **Maintained Compatibility**:
   - All enhancements are optional
   - Core marker functionality unchanged
   - Clean separation in `enhanced/` directories

3. **Improved Architecture**:
   - Cleaner configuration (reduced 378→23 lines)
   - Consolidated implementations
   - Better test organization
# Additional Marker Internals Documentation

## 7. Additional Fork Features

### LLM Image Description
**Purpose**: Generate alt text and descriptions for images in documents

**File**: `marker/processors/llm/llm_image_description.py`
**Function**: `LLMImageDescriptionProcessor.__call__()` (lines 51-125)

```python
class LLMImageDescriptionProcessor(BaseLLMSimpleBlockProcessor):
    block_types = (BlockTypes.Picture, BlockTypes.Figure,)
    
    image_description_prompt = """You are a document analysis expert...
    Create a short description of the image.
    Include numeric data if present.
    """
    
    def extract_image_data(self, document: Document, block: Block):
        # Extract image and convert to base64
        image = block.get_image(document, highres=True)
        return self.image_to_base64(image)
    
    def postprocess_response(self, document: Document, block: Block, text: str):
        # Add description as alt text
        block.alt_text = text
        block.description = text
```

**When Used**:
- When `--use_llm` flag is set
- For all Picture and Figure blocks
- Can be disabled with `--disable_image_extraction`

**Async Version**: `marker/processors/llm/llm_image_description_async.py`
- Processes multiple images concurrently
- Uses aiohttp for better performance
- Configurable batch size (default 10)
- Max concurrent images (default 5)

### Enhanced Camelot Integration
**Purpose**: Fallback table extraction for complex tables

**File**: `marker/processors/enhanced_camelot/processor.py`
**Function**: `EnhancedTableProcessor.process_table()` (lines 134-187)

```python
class EnhancedTableProcessor(TableProcessor):
    def process_table(self, document: Document, table_block: BaseTable):
        # First try standard extraction
        surya_table = self.get_table_surya(document, table_block)
        
        # Evaluate quality
        quality_score = self.evaluator.evaluate(surya_table)
        
        if quality_score < self.config.min_quality_score:
            # Fallback to Camelot
            camelot_table = self.extract_with_camelot(
                document.filepath,
                table_block
            )
            
            # Optimize parameters if needed
            if self.config.optimize:
                camelot_table = self.optimizer.optimize(
                    camelot_table,
                    self.config
                )
```

**When Camelot is Used**:
1. When standard table extraction quality is below threshold (default 0.6)
2. For tables with complex borders or merged cells
3. When table spans multiple pages (uses TableMerger)
4. When `force_camelot` config is set
5. When cell count is below `min_cell_threshold` (default 4)

**Configuration**: `marker/config/table.py`
```python
class TableConfig(BaseModel):
    use_camelot_fallback: bool = True
    min_quality_score: float = 0.6
    optimize: bool = False
    camelot_flavor: str = "auto"  # "lattice", "stream", or "auto"
```

### Image Processing Pipeline

1. **Image Extraction**:
   - During document building, images are extracted at two resolutions
   - Low-res (96 DPI) for layout detection
   - High-res (192 DPI) for OCR and descriptions

2. **Image Description Generation Timeline**:
   ```python
   # Called during processor stage if --use_llm
   if self.extract_images and block.block_type in [Picture, Figure]:
       if not block.alt_text:  # Only if no alt text exists
           description = self.generate_description(block)
           block.alt_text = description
   ```

3. **Async Processing Benefits**:
   - Can process 10 images concurrently
   - Reduces total processing time by up to 80% for image-heavy documents
   - Automatic retry on failure
   - Progress bar support

### Table Processing Enhancements

1. **Quality Evaluation** (`marker/utils/table_quality_evaluator.py`):
   - Scores extracted tables on multiple metrics:
     - Cell completeness
     - Structure integrity
     - Alignment consistency
     - Border detection
   - Returns score 0-1, triggers fallback if < threshold

2. **Parameter Optimization** (`marker/processors/table_optimizer.py`):
   - Fine-tunes extraction parameters:
     - Line width detection
     - Cell merging thresholds
     - Text density analysis
   - Iterative optimization (configurable iterations)
   - Caches optimal parameters per document

3. **Multi-Page Table Handling** (`marker/utils/table_merger.py`):
   - Detects tables continuing across pages
   - Preserves headers on each page
   - Merges rows intelligently
   - Handles column alignment variations

### Utility Enhancements

1. **Tree-Sitter Code Detection** (`marker/services/utils/tree_sitter_utils.py`):
   ```python
   LANGUAGE_MAPPINGS = {
       "python": "python",
       "javascript": "javascript", 
       "java": "java",
       # ... 100+ languages
   }
   
   def detect_language(code_block: str) -> tuple[str, float]:
       """Returns (language, confidence)"""
       parser = Parser()
       # Try multiple languages and return best match
   ```

2. **Text Chunking** (`marker/utils/text_chunker.py`):
   - Smart document splitting for LLM processing
   - Maintains semantic boundaries
   - Configurable chunk size (default 3000 chars)
   - Overlap support (default 200 chars)

3. **Embedding Support** (`marker/utils/embedding_utils.py`):
   ```python
   def get_embedding(text: str, model="text-embedding-ada-002"):
       """Generate vector embedding for text"""
       # Supports OpenAI, Vertex AI, local models
   ```

### Renderer Additions

1. **ArangoDB JSON Renderer** (`marker/renderers/arangodb_json.py`):
   - Flattens document structure for graph database
   - Creates nodes and edges
   - Includes section breadcrumbs
   - Preserves all metadata

2. **Hierarchical JSON Renderer** (`marker/renderers/hierarchical_json.py`):
   - Nested section structure
   - Parent-child relationships
   - Complete metadata hierarchy
   - Ordered content blocks

3. **Merged JSON Renderer** (`marker/renderers/merged_json.py`):
   - Combines multiple output formats
   - Flexible structure selection
   - Backward compatible
   - Configurable depth

### Performance Optimizations

1. **Batch Processing**:
   - Image descriptions: 10 concurrent
   - Table extraction: 5 concurrent
   - LLM calls: Configurable batching
   - Reduces API costs and latency

2. **Caching System**:
   - LiteLLM cache: Avoid duplicate API calls
   - Image cache: Reuse processed images
   - Table cache: Store extraction results
   - Configurable TTL and size limits

3. **Async Operations**:
   - Image processing: Full async pipeline
   - LLM calls: Async with retry
   - Concurrent block processing
   - Progress tracking

### Configuration System

1. **Unified Config Structure**:
   ```python
   {
       "llm": {
           "service": "litellm",
           "model": "vertex_ai/gemini-2.0-flash",
           "temperature": 0.3
       },
       "table": {
           "use_camelot_fallback": true,
           "min_quality_score": 0.6
       },
       "image": {
           "extract": true,
           "describe": true,
           "async": true
       }
   }
   ```

2. **Environment Variables**:
   ```bash
   LITELLM_MODEL="vertex_ai/gemini-2.0-flash"
   ENABLE_CACHE=true
   CAMELOT_FLAVOR="lattice"
   ```

3. **CLI Override**:
   ```bash
   marker_single doc.pdf \
       --config base.json \
       --table.use_camelot_fallback=false \
       --llm.model="openai/gpt-4"
   ```

### Testing Infrastructure

1. **Feature Tests** (`tests/features/`):
   - `test_image_description.py`: Image processing tests
   - `test_camelot_integration.py`: Table fallback tests  
   - `test_async_processing.py`: Async pipeline tests
   - Mock LLM responses for consistency

2. **Integration Tests** (`tests/integration/`):
   - End-to-end document processing
   - Real PDF samples
   - Performance benchmarks
   - Memory usage tracking

3. **Database Tests** (`tests/database/`):
   - ArangoDB export validation
   - Query performance tests
   - Data integrity checks
   - Vector search validation

### CLI Enhancements

1. **New Flags**:
   ```bash
   --add-summaries         # Enable section summarization
   --enable-breadcrumbs    # Add section breadcrumbs
   --use-camelot          # Force Camelot for tables
   --async-images         # Async image processing
   --cache-ttl=3600       # Cache time-to-live
   --table-quality=0.7    # Quality threshold
   ```

2. **Configuration Files**:
   ```bash
   # Use JSON config
   marker_single doc.pdf --config config.json
   
   # Use YAML config  
   marker_single doc.pdf --config config.yaml
   
   # Override specific values
   marker_single doc.pdf --config base.json --llm.model="claude-3"
   ```

3. **Batch Processing**:
   ```bash
   # Process directory
   marker_batch /input/dir --workers 8 --format json
   
   # Process with pattern
   marker_batch "*.pdf" --recursive --output /results
   
   # Resume interrupted batch
   marker_batch --resume batch_state.json
   ```

### Error Handling and Logging

1. **Structured Logging**:
   ```python
   from marker.services.utils.log_utils import log_api_request
   
   log_api_request(
       service="litellm",
       endpoint="completion",
       params={"model": model, "temperature": temp}
   )
   ```

2. **Error Recovery**:
   - Automatic retry for API failures
   - Fallback to rule-based methods
   - Partial result saving
   - Detailed error reporting

3. **Debug Mode**:
   ```bash
   marker_single doc.pdf --debug
   # Saves:
   # - Layout detection images
   # - OCR results
   # - LLM prompts/responses
   # - Processing timeline
   ```

## Summary

The enhanced Marker fork provides:

1. **Robust Table Extraction**: Camelot fallback for complex tables
2. **Image Understanding**: LLM-powered descriptions and alt text
3. **Document Structure**: Hierarchical sections with breadcrumbs
4. **Performance**: Async processing and intelligent caching
5. **Flexibility**: Multiple LLM providers via LiteLLM
6. **Database Ready**: ArangoDB export with relationships
7. **Developer Friendly**: Comprehensive testing and documentation

All enhancements are optional and maintain backward compatibility with the original Marker.