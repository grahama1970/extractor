# LiteLLM Integration in Extractor

## Overview

Successfully integrated LiteLLM support into the extractor project to replace marker's default Google Gemini service. This allows using any LLM provider supported by LiteLLM (OpenAI, Anthropic, Vertex AI, etc.) with unified interface and caching.

## What Was Done

### 1. Created LiteLLM Adapter
- `src/extractor/core/services/marker_litellm_adapter.py`
- Wraps our existing `LiteLLMService` to be compatible with marker's expected interface
- Handles marker's `format_image_for_llm` method requirement
- Manages cases where marker doesn't provide images

### 2. Enhanced Unified Extractor
- Updated `src/extractor/unified_extractor.py` to use LiteLLM when enabled
- Added ability to specify custom LLM service via config
- Integrated our enhanced table processor when LLM is enabled
- Made LLM usage optional with `use_llm` parameter

### 3. Updated Pipeline
- Modified `pipeline_orchestrator.py` to support `--llm` flag
- Without `--llm`: Uses basic marker extraction (fast, no AI enhancement)
- With `--llm`: Uses LiteLLM + enhanced table processing

## Usage

### Basic extraction (no LLM):
```bash
python src/extractor/pipeline_orchestrator.py
```

### Enhanced extraction with LiteLLM:
```bash
python src/extractor/pipeline_orchestrator.py --llm
```

## Configuration

The LiteLLM service uses these environment variables:
- `VERTEX_PROJECT` - For Google Vertex AI (default)
- `OPENAI_API_KEY` - For OpenAI models
- `ANTHROPIC_API_KEY` - For Claude models
- Other providers as supported by LiteLLM

Default model: `vertex_ai/gemini-2.5-flash`

## Architecture

```
PDF → Marker Extract → [Optional: LiteLLM Enhancement] → Gold Standard JSON
                              ↑
                    Enhanced Table Processor
                    (llm_table.py)
```

## Benefits

1. **Provider Flexibility**: Use any LLM provider via LiteLLM
2. **Caching**: Built-in caching reduces API costs
3. **Enhanced Tables**: Better table header processing with our custom processor
4. **Backward Compatible**: Can still run without LLM for fast extraction

## Next Steps

1. Test with different LLM providers
2. Fine-tune prompts for specific document types
3. Add more enhanced processors (equations, forms, etc.)
4. Consider forking marker for deeper integration