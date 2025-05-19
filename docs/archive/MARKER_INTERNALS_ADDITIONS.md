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