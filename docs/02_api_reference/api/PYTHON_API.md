# Marker Python API Reference

## Quick Start

```python
from marker.converters.pdf import PdfConverter
from marker.config.parser import ParserConfig

# Basic conversion
converter = PdfConverter()
document = converter("input.pdf")
markdown = document.export_to_markdown()

# With configuration
config = ParserConfig(
    model_list=["surya_det", "surya_rec"],
    table_extraction_enabled=True,
    image_description_enabled=True
)
converter = PdfConverter(config=config)
document = converter("input.pdf")
```

## Core Classes

### PdfConverter

Main converter class for PDF documents.

```python
class PdfConverter:
    def __init__(self, config: Optional[ParserConfig] = None)
    def __call__(self, filepath: str) -> Document
    def convert_single(self, filepath: str) -> Document
```

#### Methods

**`__init__(config)`**
- `config`: Optional configuration object
- Initializes converter with specified settings

**`convert_single(filepath)`**
- `filepath`: Path to PDF file
- Returns: `Document` object
- Converts a single PDF to Document

### Document

Represents a complete document with hierarchical structure.

```python
class Document:
    def __init__(self, filepath: str)
    
    @property
    def pages(self) -> List[Page]
    @property
    def blocks(self) -> List[Block]
    @property
    def sections(self) -> List[Dict]
    
    def export_to_markdown(self) -> str
    def export_to_json(self) -> Dict
    def export_to_html(self) -> str
```

#### Properties

**`pages`**
- List of Page objects in document

**`blocks`**
- All blocks across all pages

**`sections`**
- Section hierarchy with titles and levels

#### Methods

**`export_to_markdown()`**
- Returns markdown representation

**`export_to_json()`**
- Returns JSON structure

**`export_to_html()`**
- Returns HTML output

### Page

Represents a single page in a document.

```python
class Page:
    def __init__(self, page_id: int)
    
    @property
    def blocks(self) -> List[Block]
    @property 
    def page_number(self) -> int
    @property
    def dimensions(self) -> Dict[str, float]
```

### Block

Base class for all document blocks.

```python
class Block:
    def __init__(self, bbox: List[float])
    
    @property
    def block_type(self) -> BlockType
    @property
    def children(self) -> List[Block]
    @property
    def text(self) -> str
```

#### Block Types

- `TextBlock`: Regular text content
- `SectionHeader`: Section headings
- `TableBlock`: Tables
- `FigureBlock`: Figures and images
- `CodeBlock`: Code snippets
- `EquationBlock`: Mathematical equations
- `ListItem`: List elements

### Configuration

```python
class ParserConfig:
    def __init__(
        self,
        model_list: List[str] = None,
        device: str = "cuda",
        batch_multiplier: int = 2,
        table_extraction_enabled: bool = True,
        image_description_enabled: bool = True,
        section_summarization_enabled: bool = False,
        llm_provider: str = "litellm",
        llm_model: str = "gemini-2.0-flash-exp"
    )
```

#### Parameters

- `model_list`: Surya models to use
- `device`: Processing device (cuda/cpu)
- `batch_multiplier`: Batch size factor
- `table_extraction_enabled`: Enable table processing
- `image_description_enabled`: Generate image descriptions
- `section_summarization_enabled`: Create section summaries
- `llm_provider`: LLM service provider
- `llm_model`: Specific model to use

## Advanced Usage

### Custom Processing

```python
from marker.processors.text import TextProcessor
from marker.processors.table import TableProcessor

# Custom processor chain
processors = [
    TextProcessor(),
    TableProcessor(config={"use_camelot": True}),
]

converter = PdfConverter()
document = converter("input.pdf")

# Apply processors
for processor in processors:
    processor(document)
```

### Image Description

```python
from marker.processors.llm.llm_image_description import ImageDescriptionProcessor

# Enable image descriptions
config = ParserConfig(image_description_enabled=True)
converter = PdfConverter(config=config)

# Process with descriptions
document = converter("presentation.pdf")

# Access descriptions
for block in document.blocks:
    if block.block_type == BlockType.Figure:
        print(block.description)
```

### Section Summarization

```python
from marker.processors.section_summarizer import SectionSummarizer

# Enable summarization
config = ParserConfig(section_summarization_enabled=True)
converter = PdfConverter(config=config)

document = converter("research_paper.pdf")

# Access summaries
for section in document.sections:
    print(f"{section['title']}: {section['summary']}")
```

### Table Extraction

```python
from marker.config.table import TableConfig

# Configure table extraction
table_config = TableConfig(
    enabled=True,
    use_camelot_fallback=True,
    min_quality_score=0.6
)

config = ParserConfig()
config.table_config = table_config

converter = PdfConverter(config=config)
document = converter("spreadsheet.pdf")

# Access tables
for block in document.blocks:
    if block.block_type == BlockType.Table:
        df = block.to_dataframe()
        print(df)
```

## Integration Examples

### With LiteLLM

```python
from marker.services.litellm import LiteLLMService

# Configure LLM service
llm_service = LiteLLMService(
    model="gpt-4",
    api_key="your-api-key"
)

config = ParserConfig()
config.llm_service = llm_service

converter = PdfConverter(config=config)
```

### With ArangoDB

```python
from marker.renderers.arangodb_json import ArangoDBJsonRenderer

# Convert to ArangoDB format
document = converter("input.pdf")
renderer = ArangoDBJsonRenderer()
arango_data = renderer.render(document)

# Import to ArangoDB
from arango import ArangoClient
client = ArangoClient()
db = client.db("documents")
collection = db.collection("pdfs")
collection.insert(arango_data)
```

### Batch Processing

```python
import concurrent.futures
from pathlib import Path

def process_pdf(pdf_path):
    converter = PdfConverter()
    document = converter(pdf_path)
    output_path = pdf_path.with_suffix('.md')
    output_path.write_text(document.export_to_markdown())
    return output_path

# Process directory
pdf_files = list(Path("pdfs").glob("*.pdf"))

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    results = executor.map(process_pdf, pdf_files)
    
for result in results:
    print(f"Processed: {result}")
```

## Error Handling

```python
from marker.exceptions import ConversionError, ModelLoadError

try:
    converter = PdfConverter()
    document = converter("input.pdf")
except ModelLoadError as e:
    print(f"Failed to load model: {e}")
except ConversionError as e:
    print(f"Conversion failed: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Performance Tips

1. **Use GPU acceleration**:
   ```python
   config = ParserConfig(device="cuda")
   ```

2. **Adjust batch size**:
   ```python
   config = ParserConfig(batch_multiplier=4)
   ```

3. **Disable optional features**:
   ```python
   config = ParserConfig(
       image_description_enabled=False,
       section_summarization_enabled=False
   )
   ```

4. **Cache models**:
   ```python
   from marker.models import ModelCache
   ModelCache.preload(["surya_det", "surya_rec"])
   ```

## API Reference

For complete API documentation, see:
- [Document API](document_api.md)
- [Block Types](block_types.md)
- [Processor API](processor_api.md)
- [Configuration Reference](configuration.md)