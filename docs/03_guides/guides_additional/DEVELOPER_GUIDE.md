# Marker Developer Guide

This guide provides comprehensive information for developers working with the enhanced Marker codebase.

## Quick Start

### Basic Usage
```python
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict

converter = PdfConverter(artifact_dict=create_model_dict())
result = converter("document.pdf")
```

### With Enhancements
```python
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser

config = {
    "use_llm": True,
    "add_summaries": True,
    "enable_breadcrumbs": True,
    "output_format": "hierarchical_json"
}

parser = ConfigParser(config)
converter = PdfConverter(
    config=parser.generate_config_dict(),
    artifact_dict=create_model_dict(),
    processor_list=parser.get_processors()
)
result = converter("document.pdf")
```

## Architecture Overview

### Core Components

1. **Providers**: Load and parse input files
   - `PdfProvider`: Handles PDF files
   - `ImageProvider`: Handles image files
   - `HtmlProvider`: Handles HTML files

2. **Builders**: Create initial document structure
   - `DocumentBuilder`: Creates Document object
   - `LayoutBuilder`: Detects layout with Surya
   - `OcrBuilder`: Performs OCR with Surya
   - `StructureBuilder`: Builds document structure

3. **Processors**: Transform and enhance blocks
   - Text processors (merge lines, format)
   - Table processors (extract, optimize)
   - LLM processors (equations, images)
   - Enhancement processors (summaries, hierarchy)

4. **Renderers**: Output document in various formats
   - `MarkdownRenderer`: Markdown output
   - `HtmlRenderer`: HTML output
   - `JsonRenderer`: JSON output
   - `ArangoDBRenderer`: Database-ready JSON

### Processing Pipeline

```
Input File
    ↓
Provider → Load file, extract metadata
    ↓
Builders → Create blocks, detect layout, OCR
    ↓
Processors → Transform blocks, add features
    ↓
Renderers → Generate output format
    ↓
Output File
```

## Extension Points

### Adding a New Processor

1. **Create processor class**:
```python
from marker.processors import BaseProcessor
from marker.schema import BlockTypes

class MyProcessor(BaseProcessor):
    block_types = (BlockTypes.Text, BlockTypes.Table)
    
    def __call__(self, document: Document):
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                self.process_block(block)
    
    def process_block(self, block):
        # Your processing logic
        pass
```

2. **Register processor**:
```python
# In your converter
processor_list = [
    # ... existing processors
    MyProcessor,
]
```

### Adding a New Renderer

1. **Create renderer class**:
```python
from marker.renderers import BaseRenderer

class MyRenderer(BaseRenderer):
    def __call__(self, document: Document) -> MyOutput:
        output = MyOutput()
        for page in document.pages:
            output.add_page(self.render_page(page))
        return output
    
    def render_page(self, page):
        # Your rendering logic
        pass
```

2. **Use renderer**:
```python
converter = PdfConverter(
    renderer=MyRenderer(),
    # ... other config
)
```

### Adding a New Block Type

1. **Define block class**:
```python
from marker.schema.blocks import Block
from marker.schema import BlockTypes

class MyBlock(Block):
    block_type = BlockTypes.Custom
    my_property: str
    
    def assemble_html(self, document, child_blocks, parent_structure):
        return f"<div class='my-block'>{self.my_property}</div>"
```

2. **Register block**:
```python
from marker.schema.registry import register_block_class

register_block_class(BlockTypes.Custom, MyBlock)
```

## Configuration System

### Configuration Files

1. **JSON Configuration**:
```json
{
    "output_format": "markdown",
    "use_llm": true,
    "llm_service": "marker.services.litellm.LiteLLMService",
    "llm_config": {
        "model": "vertex_ai/gemini-2.0-flash",
        "temperature": 0.3
    },
    "table_config": {
        "use_camelot_fallback": true,
        "min_quality_score": 0.6
    }
}
```

2. **YAML Configuration**:
```yaml
output_format: markdown
use_llm: true
llm_service: marker.services.litellm.LiteLLMService
llm_config:
  model: vertex_ai/gemini-2.0-flash
  temperature: 0.3
table_config:
  use_camelot_fallback: true
  min_quality_score: 0.6
```

### Environment Variables

```bash
# LLM Configuration
export LITELLM_MODEL="vertex_ai/gemini-2.0-flash"
export GOOGLE_API_KEY="your-key"
export ENABLE_CACHE=true

# Processing Options
export MARKER_DEBUG=true
export TORCH_DEVICE="cuda"
export WORKERS=8

# Table Extraction
export CAMELOT_FLAVOR="lattice"
export TABLE_QUALITY_THRESHOLD=0.7
```

## Testing

### Running Tests

```bash
# All tests
pytest tests/

# Specific category
pytest tests/features/
pytest tests/integration/

# With coverage
pytest tests/ --cov=marker --cov-report=html

# Specific test
pytest tests/features/test_summarizer.py -v
```

### Writing Tests

1. **Unit Test Example**:
```python
def test_processor():
    document = create_test_document()
    processor = MyProcessor()
    
    result = processor(document)
    
    assert result.pages[0].blocks[0].processed == True
```

2. **Integration Test Example**:
```python
def test_full_pipeline():
    converter = PdfConverter(config=test_config)
    
    result = converter("test.pdf")
    
    assert "expected_text" in result.markdown
```

### Mocking LLM Calls

```python
from unittest.mock import patch

@patch('litellm.completion')
def test_with_llm(mock_completion):
    mock_completion.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Test response"))]
    )
    
    # Your test code
```

## Performance Optimization

### 1. Batch Processing

```python
# Process multiple files
converter = PdfConverter(
    parallel_workers=8,
    batch_size=32
)

# Process images in batches
processor = LLMImageDescriptionProcessor(
    batch_size=10,
    use_async_batch=True
)
```

### 2. Caching

```python
# Enable LLM caching
config = {
    "llm_config": {
        "enable_cache": True,
        "cache_ttl": 3600
    }
}

# Enable table cache
config = {
    "table_config": {
        "enable_cache": True,
        "cache_dir": "/tmp/marker_cache"
    }
}
```

### 3. GPU Optimization

```python
# Use specific GPU
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

# Optimize batch sizes
config = {
    "layout_batch_size": 8,
    "ocr_batch_size": 16
}
```

## Debugging

### Debug Mode

```bash
# Enable debug output
marker_single doc.pdf --debug

# Debug specific component
MARKER_DEBUG_PROCESSORS=TableProcessor,LLMImageDescriptionProcessor
```

### Debug Output

Debug mode saves:
- Layout detection images
- OCR results  
- Processing timeline
- LLM prompts/responses
- Error traces

### Common Issues

1. **Memory Issues**:
```python
# Reduce batch sizes
config = {
    "layout_batch_size": 2,
    "ocr_batch_size": 4
}

# Process in chunks
converter = PdfConverter(
    max_pages_per_chunk=10
)
```

2. **LLM Failures**:
```python
# Add retry logic
config = {
    "llm_config": {
        "max_retries": 3,
        "retry_delay": 1.0
    }
}
```

3. **Table Extraction Issues**:
```python
# Force Camelot for specific tables
config = {
    "table_config": {
        "force_camelot": True,
        "camelot_flavor": "stream"
    }
}
```

## Best Practices

### 1. Error Handling

```python
try:
    result = converter(filepath)
except ProviderError as e:
    # Handle input file issues
    logger.error(f"Failed to load file: {e}")
except ProcessorError as e:
    # Handle processing issues
    logger.error(f"Processing failed: {e}")
```

### 2. Resource Management

```python
# Use context managers
with PdfConverter(config) as converter:
    result = converter(filepath)

# Clean up resources
converter.cleanup()
```

### 3. Configuration Management

```python
# Use configuration classes
from marker.config import MarkerConfig

config = MarkerConfig(
    output_format="json",
    use_llm=True,
    llm_model="gemini-2.0-flash"
)
```

### 4. Logging

```python
from marker.logger import logger

logger.info("Starting processing")
logger.debug(f"Config: {config}")
logger.error(f"Failed: {error}")
```

## API Reference

### Key Classes

1. **Document**:
```python
class Document:
    filepath: str
    pages: List[Page]
    metadata: Dict[str, Any]
    
    def get_page(self, page_id: int) -> Page
    def get_block(self, block_id: BlockId) -> Block
    def contained_blocks(self, block_types: List[BlockTypes]) -> List[Block]
```

2. **Block**:
```python
class Block:
    block_type: BlockTypes
    block_id: int
    page_id: int
    polygon: PolygonBox
    metadata: Dict[str, Any]
    
    def raw_text(self, document: Document) -> str
    def get_image(self, document: Document) -> Image
    def assemble_html(self, document: Document) -> str
```

3. **Processor**:
```python
class BaseProcessor:
    block_types: Tuple[BlockTypes, ...]
    
    def __call__(self, document: Document) -> Document
    def process_block(self, block: Block) -> None
```

## Resources

- [Main Documentation](README.md)
- [Internals Guide](MARKER_INTERNALS.md)
- [Configuration Guide](CONFIGURATION_GUIDE.md)
- [API Reference](API_REFERENCE.md)
- [Contributing Guide](../CONTRIBUTING.md)