# Complete Extraction Pipeline Architecture

## Overview

This document provides a comprehensive walkthrough of the document extraction pipeline, explaining each stage with code examples. The pipeline transforms PDF documents into structured data while preserving user annotations as processing instructions.

## Pipeline Flow Diagram

```
┌─────────────────────┐
│   Original PDF      │
│  (with annotations) │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐     ┌────────────────────┐
│ 1. PyMuPDF Annot    │────▶│ Annotation Features│
│    Extraction       │     │ - Categories       │
└──────────┬──────────┘     │ - Bounding boxes   │
           │                │ - Instructions     │
           ▼                └────────────────────┘
┌─────────────────────┐
│  Clean PDF Created  │
│ (annotations removed)│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐     ┌────────────────────┐
│ 2. Marker PDF       │────▶│ Knowledge-First    │
│    Extraction       │     │ - ArangoDB queries │
└──────────┬──────────┘     │ - Historical data  │
           │                └────────────────────┘
           ▼
┌─────────────────────┐
│ 3. LLM Enhancement  │
│  (Claude/Gemini)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 4. Camelot Fallback │
│  (Low confidence)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 5. Post-Processing  │
│  - Validation       │
│  - Metadata         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Unified JSON       │
│     Output          │
└─────────────────────┘
```

## Stage 1: Annotation Extraction with PyMuPDF

The pipeline begins by extracting PDF annotations BEFORE any content processing. This critical step captures user instructions embedded in the PDF.

### Code: Annotation Extraction

```python
# src/extractor/core/processors/annotation_extractor.py

class AnnotationExtractor:
    def extract_annotations(self, pdf_path: str, remove_from_pdf: bool = False) -> Dict[str, Any]:
        """Extract all annotations from PDF and categorize them."""
        doc = fitz.open(pdf_path)
        
        for page_num, page in enumerate(doc):
            for annot in page.annots():
                annot_data = {
                    "page": page_num,
                    "type": annot.type[1],  # Human-readable type
                    "content": annot.info.get("content", ""),
                    "rect": list(annot.rect),  # [x0, y0, x1, y1]
                    "colors": self._extract_colors(annot),
                    "instruction": None,  # Will be set by categorization
                    "hash": self._create_annotation_hash(page_num, annot)
                }
                
                # Categorize the annotation
                instruction = self._categorize_annotation(annot_data)
                annot_data["instruction"] = instruction
```

### Annotation Categories

```python
def _categorize_annotation(self, annot_data: Dict[str, Any]) -> str:
    """Categorize annotation by type and color only - NO content interpretation.
    
    The actual content text is stored as-is and interpreted by downstream
    processors or LLMs. We only categorize by visual properties here.
    """
    annot_type = annot_data.get("type", "")
    
    # Only categorize by visual properties (colors)
    if annot_type == "Square":
        stroke = annot_data.get("colors", {}).get("stroke", [])
        if stroke and len(stroke) >= 3:
            # Green box (high green component, low red/blue)
            if stroke[1] > 0.9 and stroke[0] < 0.1 and stroke[2] < 0.1:
                return "GREEN_BOX"
            # Orange box
            elif stroke[0] > 0.9 and stroke[1] > 0.1 and stroke[1] < 0.7:
                return "ORANGE_BOX"
            # Blue box
            elif stroke[2] > 0.9 and stroke[0] < 0.2:
                return "BLUE_BOX"
    
    # Return annotation type as category (Highlight, Comment, etc.)
    return annot_type.upper() if annot_type else "ANNOTATION"
```

The key improvement here is that we:
- Store the annotation content text as-is without interpretation
- Only categorize by visual properties (color, type)
- Let downstream processors or LLMs interpret the meaning of "merge table" or "section header" in context

### Creating Clean PDF

```python
def _create_clean_pdf(self, doc, original_path: str) -> str:
    """Create a PDF without annotations for clean text extraction."""
    clean_path = Path(original_path).parent / f"clean_{Path(original_path).name}"
    
    # Remove all annotations
    for page in doc:
        for annot in page.annots():
            page.delete_annot(annot)
    
    doc.save(str(clean_path))
    return str(clean_path)
```

## Stage 2: Marker PDF Extraction

With annotations removed, the clean PDF is processed by marker-pdf for structure extraction.

### Code: Pipeline Configuration

```python
# src/extractor/unified_extractor.py

async def extract_to_unified_json(
    pdf_path: str, 
    use_llm: bool = True,
    pipeline_config: Optional['PipelineConfig'] = None,
    use_knowledge_aware: bool = False
) -> Dict[str, Any]:
    
    # STEP 1: Extract annotations FIRST if configured
    annotations = None
    if pipeline_config:
        annot_config = pipeline_config.get_processor(ProcessorType.ANNOTATION_EXTRACTION)
        if annot_config and annot_config.enabled:
            logger.info("Extracting PDF annotations first...")
            extractor = AnnotationExtractor()
            
            # Extract annotations and create clean PDF
            annot_result = extractor.extract_annotations(pdf_path_str, remove_from_pdf=True)
            if annot_result["success"]:
                annotations = annot_result
                logger.success(f"Extracted {len(annot_result['annotations'])} annotations")
                
                # Use clean PDF for further processing
                if "clean_pdf_path" in annot_result:
                    logger.info(f"Using clean PDF for processing: {annot_result['clean_pdf_path']}")
                    pdf_path_str = annot_result["clean_pdf_path"]
```

### Custom Processors

The pipeline selectively replaces marker's processors with enhanced versions:

```python
# Replace marker's processors with our enhanced versions
if "SectionHeaderProcessor" in p:
    # Use knowledge-aware or enhanced section header processor
    if use_knowledge_aware:
        enhanced_processors.append("extractor.core.processors.knowledge_aware_sectionheader.KnowledgeAwareSectionHeaderProcessor")
    else:
        enhanced_processors.append("extractor.core.processors.sectionheader.SectionHeaderProcessor")
elif "TableProcessor" in p and "LLM" not in p:
    # Use our enhanced table processor with validation
    enhanced_processors.append("extractor.core.processors.table.TableProcessor")
elif "LLMTableProcessor" in p and use_llm:
    # Use our enhanced LLM table processor
    enhanced_processors.append("extractor.core.processors.llm.llm_table.LLMTableProcessor")
```

## How Downstream Processors Use Annotations

Instead of hardcoding interpretations, downstream processors receive the raw annotation data and can interpret it in context:

```python
# Example: Table processor checking for user instructions
def process_table(self, block, annotations):
    # Get annotations that overlap with this table
    relevant_annots = self.get_overlapping_annotations(block.bbox, annotations)
    
    for annot in relevant_annots:
        # The raw text is available for interpretation
        user_text = annot.get('content', '').lower()
        
        # LLM can interpret in context
        if self.use_llm:
            prompt = f"""
            The user added this annotation to a table: "{user_text}"
            The annotation is a {annot['type']} (color: {annot.get('colors', {})})
            
            Based on this instruction and the table content, what should we do?
            """
            action = self.llm_service.interpret_annotation(prompt, table_image)
        else:
            # Simple rule-based fallback
            if 'merge' in user_text and 'table' in user_text:
                self.attempt_table_merge(block)
```

This approach:
- Preserves the exact user text without interpretation
- Allows context-aware understanding by LLMs
- Enables learning from patterns over time
- Avoids brittle hardcoded rules

## Stage 3: Knowledge-First Architecture

Processors query ArangoDB for historical patterns instead of using hardcoded rules.

### Code: Real ArangoDB Queries

```python
# src/extractor/core/processors/knowledge_aware_base.py

class KnowledgeAwareProcessor(BaseProcessor, ABC):
    def _call_arango(self, method: str, **kwargs) -> Dict[str, Any]:
        """Direct call to ArangoDB worker - NO Task() prompts!"""
        try:
            args_json = json.dumps(kwargs)
            result = subprocess.run(
                [sys.executable, ARANGO_WORKER_PATH, method, args_json],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
```

### BM25 Text Search

```python
async def _query_knowledge_architect(self, features: Dict[str, Any]) -> Dict[str, Any]:
    """REAL ArangoDB queries - NO MORE Task() PROMPTS!"""
    
    # 1. BM25 Text Search
    if features.get('text'):
        bm25_query = f"""
        FOR doc IN pdf_objects
          FILTER doc.text_content != null
          LET score = BM25(doc.text_content, @search_text)
          FILTER score > 0.1
          SORT score DESC
          LIMIT 10
          RETURN {{
            case_id: doc._key,
            text: doc.text_content,
            block_type: doc.object_type,
            score: score,
            confidence: score,
            match_type: 'bm25'
          }}
        """
        
        bm25_result = self._call_arango(
            "query",
            aql=bm25_query,
            bind_vars=json.dumps({"search_text": features['text'][:500]})
        )
```

### Semantic Search with FAISS

```python
# Build FAISS index if needed for semantic search
if not similarity_matches and features.get('text'):
    # First ensure we have an index
    index_result = self._call_arango(
        "build_faiss_index",
        collection="pdf_objects",
        text_field="text_content",
        filters=json.dumps({"object_type": features.get('block_type', 'Text')})
    )
    
    if index_result.get("success"):
        # Now do semantic search
        semantic_result = self._call_arango(
            "semantic_search",
            collection="pdf_objects",
            query=features['text'][:500],
            text_field="text_content",
            top_k=5
        )
```

## Stage 4: LLM Enhancement

When enabled, the LLM processes tables with intelligent understanding of split headers.

### Code: LLM Table Processing

```python
# src/extractor/core/processors/llm/llm_table.py

class LLMTableProcessor(BaseLLMComplexBlockProcessor):
    table_rewriting_prompt = """You are a text correction expert specializing in accurately reproducing tables from images.

You will receive an image and an HTML representation of the table in the image.

**Important Note**: If the initial OCR detection found a table but marker extraction failed or had low confidence, we may have used Camelot extraction with lattice mode (line_width=15) as a fallback.

Your task is to correct any errors in the HTML representation. 

Some guidelines:
- For table header cells (`<th>`) that contain a single word split across multiple lines with a line break (for example, "Description"), join the fragments into a single complete word ("Description"). Only keep `<br>` or `<p>` inside header cells if the lines represent distinct words or concepts, not a single word split due to formatting.
- Fix stray characters, broken formatting, or obvious OCR errors.
- If the table was extracted using Camelot (check metadata), pay special attention to verifying cell boundaries and merged cells are correctly represented.

Instructions:
1. Carefully examine the provided table image.
2. Analyze the supplied HTML representation.
3. Write a comparison of the table image and the HTML, with particular attention to any multi-line column headers split by a break, ensuring they match the correct column values.
4. If the HTML representation is completely correct, or if you cannot read the image properly, then write "No corrections needed." If the HTML representation has errors, generate only the corrected HTML representation.
"""
```

### Processing Pipeline

```python
def process_rewriting(self, document: Document, page: PageGroup, block: Table):
    """
    Process table extraction following the complete pipeline:
    1. OCR page (is there a table) - already done by marker
    2. Marker (can I extract an actual table) - check children
    3. If no, use Camelot to try to extract the table/s
    4. Use pandas to analyze the table
    5. Look for similar annotation with feature relevance from ArangoDB
    6. Feed all results to the LLM prompt
    """
    # Initialize metadata
    extraction_metadata = {
        MetadataKey.OCR_DETECTED_TABLE.value: True,
        MetadataKey.MARKER_EXTRACTED.value: False,
        MetadataKey.CAMELOT_EXTRACTED.value: False,
    }
    
    # Check if marker extracted table cells
    children: List[TableCell] = block.contained_blocks(document, (BlockTypes.TableCell,))
    
    if children and len(children) > 0:
        extraction_metadata[MetadataKey.MARKER_EXTRACTED.value] = True
        logger.info(f"Marker extracted {len(children)} cells")
    else:
        # Use Camelot as fallback
        logger.info("No cells extracted by marker, attempting Camelot extraction")
        camelot_cells = self.extract_table_with_camelot(document, page, block)
```

## Stage 5: Camelot Fallback

Tables with low confidence scores or extraction failures trigger Camelot processing.

### Code: Failed Table Detection

```python
# src/extractor/unified_extractor.py

def detect_failed_table_extraction(blocks: List[Dict]) -> List[Dict]:
    """Detect tables that failed extraction and need Camelot fallback."""
    failed_tables = []
    for block in blocks:
        if block.get("block_type") == "Table":
            # Check various failure indicators
            text = block.get("text", "")
            html = block.get("html", "")
            
            # Failure indicators:
            # 1. Empty or very short text AND no/poor HTML
            if (not text or len(text) < 10) and (not html or len(html) < 50):
                failed_tables.append(block)
                continue
                
            # 2. No HTML content or null string
            if not html or html == "null" or html == "None":
                failed_tables.append(block)
                continue
                
            # 3. Text looks like JSON (common marker failure pattern)
            if text.strip().startswith("[{") and text.strip().endswith("}]"):
                failed_tables.append(block)
                continue
                
            # 4. Low confidence score if available
            confidence = block.get("metadata", {}).get("confidence", 1.0)
            if confidence < 0.5:
                failed_tables.append(block)
                continue
```

### Camelot Processing

```python
def extract_table_with_camelot(self, document: Document, page: PageGroup, block: Table) -> Optional[List[TableCell]]:
    """
    Extract table using Camelot when OCR detects a table but marker can't find it properly.
    Uses lattice mode with line_width=15 as specified.
    """
    # Get table bbox in PDF coordinates
    bbox = block.polygon.bbox
    
    # Extract table using Camelot with lattice mode and line_width=15
    logger.info(f"Attempting Camelot extraction for table on page {page_num} with bbox {bbox}")
    
    # Use table area to focus extraction
    table_area = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
    
    tables = camelot.read_pdf(
        pdf_path,
        pages=str(page_num),
        flavor='lattice',
        line_scale=15,  # line_width parameter as specified
        table_areas=[table_area],
        strip_text='\n'
    )
```

## Stage 6: Post-Processing

The pipeline applies various post-processors based on configuration.

### Section Metadata Propagation

```python
# Propagating section metadata to all blocks
from extractor.core.processors.section_metadata_propagator import (
    SectionMetadataPropagator, 
    organize_blocks_into_sections
)

propagator = SectionMetadataPropagator()
all_blocks = propagator.process_blocks(all_blocks)

# Organize into gold standard section structure
section_structure = organize_blocks_into_sections(all_blocks)
```

### Validation

```python
# Stage validation at each step
if require_gold_standard_validation:
    validator = StageValidator()
    
    # Stage 1: Annotation extraction
    stage1_result = validator.validate_stage1_annotations(
        annot_result.get('annotations', []), 
        pdf_name
    )
    
    if not validator.require_minimum_score(0.9):
        logger.error("Stage 1 validation failed - quality below 90%")
        raise ValueError("Stage 1 validation failed")
```

## Output Format

The pipeline produces a unified JSON structure:

```json
{
    "success": true,
    "data": {
        "vertices": {
            "documents": [{
                "_id": "documents/doc_123",
                "title": "Document Title",
                "metadata": {...}
            }],
            "sections": [{
                "_id": "sections/sec_456",
                "title": "Section Header",
                "level": 1,
                "content": "Section content..."
            }],
            "tables": [{
                "_id": "tables/tbl_789",
                "html": "<table>...</table>",
                "extraction_metadata": {
                    "marker_extracted": true,
                    "camelot_extracted": false,
                    "confidence": 0.95
                }
            }]
        },
        "edges": {
            "contains": [
                {"_from": "documents/doc_123", "_to": "sections/sec_456", "type": "section"},
                {"_from": "sections/sec_456", "_to": "tables/tbl_789", "type": "table"}
            ]
        },
        "all_blocks": [
            {
                "block_type": "SectionHeader",
                "text": "1. Introduction",
                "page": 0,
                "bbox": [100, 200, 300, 220],
                "metadata": {
                    "confidence": 0.98,
                    "section_level": 1,
                    "section_hash": "abc123"
                }
            }
        ]
    }
}
```

## Key Design Principles

### 1. Annotation-First Processing
- Annotations are extracted BEFORE content processing
- They serve as processing instructions, not content
- Clean PDF ensures marker isn't confused by visual overlays

### 2. No Hardcoded Fixes
- NO hardcoded word splits (e.g., "Descripti" + "on")
- Rule-based logic only (e.g., headers ending with commas)
- LLM handles intelligent corrections based on images

### 3. Knowledge-First Architecture
- Real ArangoDB queries, not dummy functions
- BM25 text search for exact matches
- Semantic search for conceptual similarity
- Graph traversal for relationship patterns

### 4. Graceful Fallbacks
- Marker → Camelot for table extraction
- LLM enhancement is optional
- Each stage validates and can fail gracefully

### 5. Preservation of Original Content
- Marker's output is preserved (including split headers)
- Post-processing agents (Claude) handle understanding
- No information is lost, only enhanced

## Usage Example

```python
from extractor.unified_extractor import extract_to_unified_json
from extractor.pipeline_config import PipelineConfig

# Configure pipeline
pipeline_config = PipelineConfig.default_config("document.pdf")

# Extract with all features enabled
result = await extract_to_unified_json(
    pdf_path="document.pdf",
    use_llm=True,                          # Enable LLM enhancement
    pipeline_config=pipeline_config,        # Use pipeline configuration
    use_knowledge_aware=True,               # Enable knowledge queries
    require_gold_standard_validation=True   # Validate at each stage
)

if result["success"]:
    # Access extracted data
    blocks = result["data"]["all_blocks"]
    sections = result["data"]["vertices"]["sections"]
    tables = result["data"]["vertices"]["tables"]
    
    # Annotations are preserved in metadata
    for block in blocks:
        if block.get("metadata", {}).get("annotation_guided"):
            print(f"Block was processed with annotation guidance")
```

## Conclusion

This pipeline represents a sophisticated approach to document extraction that:
- Respects user annotations as processing instructions
- Leverages AI for intelligent understanding
- Maintains a knowledge graph of patterns
- Provides multiple fallback mechanisms
- Preserves all original content

The key innovation is treating PDF annotations as a separate instruction layer, extracting them first, then using them to guide processing while keeping the actual content extraction clean and unbiased.