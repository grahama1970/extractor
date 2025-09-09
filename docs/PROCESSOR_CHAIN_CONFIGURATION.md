# Processor Chain Configuration System

## Overview

The Processor Chain Configuration system provides a flexible way to control which processors run during PDF extraction and in what order. This allows for customizable extraction pipelines tailored to specific document types or processing requirements.

## Key Components

### 1. PipelineConfig
The main configuration class that defines the extraction pipeline:

```python
from extractor.pipeline_config import PipelineConfig, ProcessorType

# Create default configuration
config = PipelineConfig.default_config("document.pdf")

# Create custom configuration
config = PipelineConfig(
    pdf_path="document.pdf",
    output_formats=[OutputFormat.GOLD_STANDARD],
    processors=[
        ProcessorConfig(
            name="extraction",
            type=ProcessorType.MARKER_EXTRACTION,
            settings={"use_llm": True}
        ),
        ProcessorConfig(
            name="cleaning",
            type=ProcessorType.TEXT_CLEANING,
            settings={"fix_ligatures": True}
        )
    ]
)
```

### 2. ProcessorType Enum
Defines the types of processors available:

- `MARKER_EXTRACTION` - Extract blocks from PDF using Marker
- `TEXT_CLEANING` - Clean OCR text (ligatures, encoding, etc.)
- `BLOCK_VERIFICATION` - Verify and fix mislabeled blocks
- `SECTION_HEADER_DETECTION` - Detect section headers
- `HIERARCHY_BUILDER` - Build document hierarchy and propagate section metadata
- `OUTPUT_RENDERER` - Render final output format

### 3. ProcessorConfig
Configuration for individual processors:

```python
ProcessorConfig(
    name="text_cleaner",
    type=ProcessorType.TEXT_CLEANING,
    enabled=True,
    settings={
        "fix_ligatures": True,
        "normalize_whitespace": True,
        "remove_hyphenation": False
    },
    depends_on=ProcessorType.MARKER_EXTRACTION
)
```

## Default Pipeline

The default pipeline includes these steps:

1. **Marker Extraction** - Extract blocks from PDF with optional LLM enhancement
2. **Text Cleaning** - Fix OCR issues (ligatures, encoding, whitespace)
3. **Block Verification** - Fix mislabeled blocks using suspicious header detection
4. **Hierarchy Builder** - Build document structure and add section metadata
5. **Output Renderer** - Generate final output format

## Usage Examples

### Basic Usage with Default Pipeline

```python
from extractor.pipeline_orchestrator import extract_pdf
from extractor.pipeline_config import PipelineConfig

# Use default pipeline
config = PipelineConfig.default_config("document.pdf")
result = await extract_pdf("document.pdf", pipeline_config=config)
```

### Minimal Extraction (No Post-Processing)

```python
# Create minimal config with just extraction
config = PipelineConfig(
    pdf_path="document.pdf",
    processors=[]  # No post-processing
)
result = await extract_pdf("document.pdf", pipeline_config=config)
```

### Custom Pipeline Configuration

```python
# Create custom pipeline
config = PipelineConfig.default_config("document.pdf")

# Disable specific processor
config.disable_processor(ProcessorType.TEXT_CLEANING)

# Update processor settings
config.update_processor_settings(
    ProcessorType.HIERARCHY_BUILDER,
    {"add_breadcrumbs": False}
)

# Save configuration for reuse
config.save(Path("my_config.json"))

# Load saved configuration
loaded_config = PipelineConfig.load(Path("my_config.json"))
```

### Conditional Processing

```python
# Different pipelines for different document types
if is_scanned_document:
    config = PipelineConfig.default_config(pdf_path)
    config.update_processor_settings(
        ProcessorType.TEXT_CLEANING,
        {"aggressive_cleaning": True}
    )
else:
    config = PipelineConfig(
        pdf_path=pdf_path,
        processors=[
            ProcessorConfig(
                name="fast_extraction",
                type=ProcessorType.MARKER_EXTRACTION,
                settings={"use_llm": False}
            )
        ]
    )
```

## Processor Details

### Text Cleaning Processor
Cleans OCR text issues:
- Fixes ligatures (ﬁ → fi, ﬂ → fl)
- Normalizes quotes and dashes
- Fixes encoding issues
- Removes hyphenation at line breaks
- Normalizes whitespace

Settings:
```python
{
    "fix_ligatures": True,
    "normalize_whitespace": True,
    "fix_encoding": True,
    "remove_hyphenation": True,
    "aggressive_cleaning": False
}
```

### Hierarchy Builder Processor
Builds document structure:
- Identifies real section headers
- Propagates section metadata to all blocks
- Creates hierarchical structure
- Adds section_titles, section_hashes, section_number, section_level

Settings:
```python
{
    "add_breadcrumbs": True,
    "merge_contiguous_text": True,
    "skip_false_headers": True
}
```

### Block Verification Processor
Fixes mislabeled blocks:
- Detects suspicious headers
- Uses annotation rules
- Optional LLM verification

Settings:
```python
{
    "mode": "suspicious_only",
    "use_annotation_rules": True,
    "use_llm_verification": False,
    "llm_confidence_threshold": 0.85
}
```

## Integration with Unified Extractor

The pipeline configuration integrates seamlessly with the unified extractor:

```python
async def extract_to_unified_json(
    pdf_path: str,
    use_llm: bool = True,
    use_pymupdf: bool = False,
    pipeline_config: Optional[PipelineConfig] = None
) -> Dict[str, Any]:
    """Extract PDF with optional pipeline configuration."""
    
    # ... extraction logic ...
    
    if pipeline_config:
        # Apply configured processors
        for processor_config in pipeline_config.get_enabled_processors():
            processor = ProcessorRegistry.create_processor(processor_config)
            if processor:
                all_blocks = processor.process_blocks(all_blocks)
    else:
        # Use default processing
        # ...
```

## Adding New Processors

To add a new processor:

1. Add new type to ProcessorType enum
2. Create processor class with `process_blocks` method
3. Register in ProcessorRegistry
4. Add to pipeline configuration

Example:
```python
# 1. Add to ProcessorType enum
class ProcessorType(Enum):
    # ...
    CUSTOM_PROCESSOR = "custom_processor"

# 2. Create processor class
class CustomProcessor:
    def __init__(self, **settings):
        self.settings = settings
    
    def process_blocks(self, blocks: List[Dict]) -> List[Dict]:
        # Process blocks
        return blocks

# 3. Register processor
ProcessorRegistry.register(
    ProcessorType.CUSTOM_PROCESSOR,
    CustomProcessor
)
```

## Best Practices

1. **Start with Default Pipeline** - The default configuration handles most common cases
2. **Disable Rather Than Remove** - Use `disable_processor()` to turn off processors
3. **Save Configurations** - Save working configurations for reuse
4. **Test Incrementally** - Test each processor independently before combining
5. **Monitor Performance** - Some processors (like LLM-based ones) add latency
6. **Use Appropriate Settings** - Match processor settings to document characteristics

## Debugging

Enable debug mode to see processor execution:

```python
config = PipelineConfig.default_config("document.pdf")
config.debug_mode = True
```

This will log:
- Which processors are running
- Processing time for each processor
- Number of blocks before/after processing
- Any errors or warnings

## Performance Considerations

- **Marker Extraction**: Slowest step, especially with LLM enhancement
- **Text Cleaning**: Fast, minimal overhead
- **Hierarchy Builder**: Fast, scales with document size
- **Block Verification**: Can be slow with LLM verification enabled

For maximum speed, use minimal pipeline:
```python
config = PipelineConfig(
    pdf_path="document.pdf",
    processors=[],  # Skip all post-processing
    output_formats=[OutputFormat.JSON]
)
```

For maximum accuracy, use full pipeline with LLM:
```python
config = PipelineConfig.default_config("document.pdf")
config.update_processor_settings(
    ProcessorType.MARKER_EXTRACTION,
    {"use_llm": True, "llm_model": "vertex_ai/gemini-2.5-pro"}
)
```