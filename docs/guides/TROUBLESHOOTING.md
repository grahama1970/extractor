# Marker Troubleshooting Guide

## Common Issues and Solutions

### Installation Problems

#### CUDA/GPU Issues
**Problem**: `RuntimeError: CUDA out of memory`

**Solution**:
```python
# Reduce batch size
config = ParserConfig(batch_multiplier=1)

# Or use CPU
config = ParserConfig(device="cpu")
```

#### Model Download Failures
**Problem**: `ModelLoadError: Failed to download surya_det`

**Solution**:
1. Check internet connection
2. Manually download models:
   ```bash
   marker download-models --model surya_det
   ```
3. Set custom model path:
   ```python
   os.environ["TORCH_HOME"] = "/path/to/models"
   ```

### Conversion Errors

#### Corrupted PDF
**Problem**: `PyPDF2.errors.PdfReadError: EOF marker not found`

**Solution**:
```python
# Try repairing PDF first
import pikepdf

pdf = pikepdf.open("corrupted.pdf")
pdf.save("repaired.pdf")

# Then convert
converter = PdfConverter()
document = converter("repaired.pdf")
```

#### Memory Issues
**Problem**: `MemoryError` during conversion

**Solution**:
```python
# Process in chunks
config = ParserConfig(
    batch_multiplier=1,
    page_chunk_size=5
)

# Or increase system swap
```

### Table Extraction Issues

#### Tables Not Detected
**Problem**: Tables appear as text blocks

**Solution**:
```python
# Enable Camelot fallback
config = ParserConfig()
config.table_config.use_camelot_fallback = True

# Or adjust detection threshold
config.table_config.min_cells = 2
```

#### Malformed Tables
**Problem**: Table structure is incorrect

**Solution**:
```python
# Use table optimizer
config.table_config.optimize = True

# Or extract manually
from camelot import read_pdf
tables = read_pdf("input.pdf", pages="1")
```

### LLM Integration Issues

#### API Key Errors
**Problem**: `AuthenticationError: Invalid API key`

**Solution**:
```python
# Set environment variable
os.environ["OPENAI_API_KEY"] = "your-key"

# Or configure directly
config = ParserConfig()
config.llm_config.api_key = "your-key"
```

#### Rate Limiting
**Problem**: `RateLimitError: Too many requests`

**Solution**:
```python
# Add retry logic
from tenacity import retry, wait_exponential

@retry(wait=wait_exponential(multiplier=1, min=4, max=10))
def process_with_llm(document):
    return llm_processor(document)

# Or reduce concurrent requests
config.llm_config.max_concurrent = 1
```

### Performance Issues

#### Slow Processing
**Problem**: Conversion takes too long

**Solution**:
```python
# Profile bottlenecks
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

document = converter("input.pdf")

profiler.disable()
stats = pstats.Stats(profiler)
stats.print_stats()

# Common optimizations:
# 1. Use GPU
config = ParserConfig(device="cuda")

# 2. Increase batch size
config = ParserConfig(batch_multiplier=4)

# 3. Disable optional features
config = ParserConfig(
    image_description_enabled=False,
    section_summarization_enabled=False
)
```

#### High Memory Usage
**Problem**: Process uses excessive RAM

**Solution**:
```python
# Monitor memory usage
import psutil
import os

process = psutil.Process(os.getpid())
print(f"Memory: {process.memory_info().rss / 1024 / 1024:.2f} MB")

# Reduce memory:
# 1. Process pages individually
for page_num in range(pdf.page_count):
    page_doc = converter.convert_page("input.pdf", page_num)
    
# 2. Clear cache regularly
import gc
gc.collect()

# 3. Use smaller models
config = ParserConfig(model_variant="small")
```

### Output Quality Issues

#### Missing Text
**Problem**: Some text not extracted

**Solution**:
```python
# Adjust OCR settings
config = ParserConfig()
config.ocr_config.confidence_threshold = 0.5
config.ocr_config.enable_enhancement = True

# Or try different extraction method
from pdfplumber import PDF
with PDF.open("input.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text()
```

#### Wrong Section Hierarchy
**Problem**: Headers not properly detected

**Solution**:
```python
# Adjust header detection
config = ParserConfig()
config.header_config.font_size_threshold = 14
config.header_config.font_weight_threshold = 500

# Or manually correct
document = converter("input.pdf")
for block in document.blocks:
    if should_be_header(block):
        block.block_type = BlockType.SectionHeader
        block.level = calculate_level(block)
```

### CLI Issues

#### Command Not Found
**Problem**: `bash: marker: command not found`

**Solution**:
```bash
# Reinstall with CLI extras
pip install marker-pdf[cli]

# Or use python module
python -m marker.cli convert input.pdf
```

#### Invalid Arguments
**Problem**: `Error: Invalid value for '--config'`

**Solution**:
```bash
# Check help
marker convert --help

# Use correct syntax
marker convert input.pdf --config.table.enabled=true

# Or use config file
marker convert input.pdf --config-file config.json
```

## Debug Mode

Enable detailed logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or via CLI
marker convert input.pdf --debug
```

## Getting Help

1. Check the [FAQ](FAQ.md)
2. Search [GitHub Issues](https://github.com/USERNAME/marker/issues)
3. Enable debug logging and check output
4. Create minimal reproducible example
5. Open new issue with:
   - Error message
   - Debug logs
   - Sample PDF (if possible)
   - Environment details

## Environment Debugging

```python
# Print environment info
from marker.util import print_debug_info
print_debug_info()

# Output includes:
# - Python version
# - Package versions
# - GPU availability
# - Model paths
# - Configuration
```