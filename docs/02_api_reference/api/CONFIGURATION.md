# Marker Configuration Guide

## Overview

Marker provides extensive configuration options to customize the PDF conversion process. Configuration can be provided via code, CLI arguments, or configuration files.

## Configuration Methods

### 1. Python Code
```python
from marker.config.parser import ParserConfig

config = ParserConfig(
    device="cuda",
    batch_multiplier=2,
    table_extraction_enabled=True
)
```

### 2. CLI Arguments
```bash
marker convert input.pdf --config.device=cuda --config.batch_multiplier=2
```

### 3. Configuration File
```json
{
  "device": "cuda",
  "batch_multiplier": 2,
  "table_extraction_enabled": true
}
```

```bash
marker convert input.pdf --config-file config.json
```

## Main Configuration Options

### ParserConfig

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `device` | str | "cuda" | Processing device ("cuda" or "cpu") |
| `model_list` | List[str] | ["surya_det", "surya_rec"] | Models to use |
| `batch_multiplier` | int | 2 | Batch size multiplier |
| `page_chunk_size` | int | 10 | Pages to process at once |
| `debug` | bool | False | Enable debug logging |

### Table Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `table_extraction_enabled` | bool | True | Enable table extraction |
| `use_camelot_fallback` | bool | True | Use Camelot for complex tables |
| `min_cells` | int | 4 | Minimum cells to detect table |
| `min_quality_score` | float | 0.6 | Minimum table quality |
| `optimize` | bool | False | Enable table optimization |

### OCR Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `ocr_enabled` | bool | True | Enable OCR processing |
| `confidence_threshold` | float | 0.7 | OCR confidence threshold |
| `enable_enhancement` | bool | True | Enable image enhancement |
| `languages` | List[str] | ["en"] | OCR languages |

### LLM Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `llm_provider` | str | "litellm" | LLM service provider |
| `llm_model` | str | "gemini-2.0-flash-exp" | Model to use |
| `api_key` | str | None | API key (or use env var) |
| `max_concurrent` | int | 5 | Max concurrent requests |
| `timeout` | int | 30 | Request timeout (seconds) |

### Image Description

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `image_description_enabled` | bool | False | Generate image descriptions |
| `description_model` | str | None | Override model for descriptions |
| `min_image_size` | int | 100 | Minimum image dimension |
| `max_description_length` | int | 500 | Maximum description length |

### Section Summarization

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `section_summarization_enabled` | bool | False | Create section summaries |
| `summary_model` | str | None | Override model for summaries |
| `min_section_length` | int | 200 | Minimum section length |
| `max_summary_length` | int | 150 | Maximum summary length |

## Advanced Configuration

### Custom Model Paths
```python
config = ParserConfig()
config.model_config.surya_det_path = "/custom/path/surya_det.pth"
config.model_config.surya_rec_path = "/custom/path/surya_rec.pth"
```

### Memory Management
```python
config = ParserConfig()
config.memory_config.max_memory_gb = 8
config.memory_config.clear_cache_frequency = 10
config.memory_config.use_fp16 = True
```

### Performance Tuning
```python
config = ParserConfig()
config.performance_config.num_workers = 4
config.performance_config.prefetch_pages = 5
config.performance_config.cache_models = True
```

## Configuration Profiles

### High Quality
```python
high_quality_config = ParserConfig(
    device="cuda",
    batch_multiplier=1,
    ocr_config={
        "confidence_threshold": 0.9,
        "enable_enhancement": True
    },
    table_config={
        "optimize": True,
        "min_quality_score": 0.8
    }
)
```

### Fast Processing
```python
fast_config = ParserConfig(
    device="cuda",
    batch_multiplier=4,
    image_description_enabled=False,
    section_summarization_enabled=False,
    table_config={
        "optimize": False,
        "use_camelot_fallback": False
    }
)
```

### Low Memory
```python
low_memory_config = ParserConfig(
    device="cpu",
    batch_multiplier=1,
    page_chunk_size=5,
    memory_config={
        "clear_cache_frequency": 5,
        "use_fp16": True
    }
)
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `MARKER_DEVICE` | Default device | `cuda` |
| `MARKER_MODEL_PATH` | Model directory | `/models/marker` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic API key | `sk-ant-...` |
| `GEMINI_API_KEY` | Google API key | `AIza...` |

## Configuration Validation

```python
from marker.config.validator import validate_config

config = ParserConfig(...)
errors = validate_config(config)
if errors:
    print(f"Configuration errors: {errors}")
```

## Best Practices

1. **Start with defaults**: Only override what you need
2. **Test configurations**: Benchmark different settings
3. **Monitor resources**: Watch memory and GPU usage
4. **Use profiles**: Create reusable configuration profiles
5. **Environment-specific**: Different configs for dev/prod

## Troubleshooting Configuration

### Common Issues

1. **CUDA out of memory**
   - Reduce `batch_multiplier`
   - Lower `page_chunk_size`
   - Enable FP16 mode

2. **Slow processing**
   - Increase `batch_multiplier`
   - Enable GPU acceleration
   - Disable optional features

3. **Poor quality output**
   - Increase `confidence_threshold`
   - Enable `optimize` for tables
   - Use higher quality models

### Debug Configuration

```python
# Print effective configuration
print(config.to_dict())

# Validate configuration
from marker.config.validator import validate_config
errors = validate_config(config)

# Log configuration
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("marker.config")
```