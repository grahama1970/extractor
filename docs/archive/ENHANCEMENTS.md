# Marker Enhancements

This document describes the enhancements made to the Marker PDF converter for specific use cases.

## Key Features Added

### 1. Section Breadcrumbs
- **Purpose**: Enable hierarchical navigation and ArangoDB insertion
- **Implementation**: Added to `SectionHeader` schema
- **Usage**: `--enable-breadcrumbs` flag

### 2. LLM Model Selection
- **Purpose**: Flexibility in model provider choice (cost/performance optimization)
- **Implementation**: LiteLLM service integration
- **Usage**: `--llm_service` and `--model` flags

### 3. Document Hierarchy
- **Purpose**: Transform flat structure into hierarchical with sections as containers
- **Implementation**: `HierarchyBuilder` processor
- **Usage**: `--output_format hierarchical_json`

### 4. Section Summaries
- **Purpose**: Automatic summarization of document sections
- **Implementation**: `SimpleSectionSummarizer` processor
- **Usage**: `--add-summaries` flag

## Quick Start

```bash
# Convert with all enhancements
marker_single document.pdf \
  --add-summaries \
  --enable-breadcrumbs \
  --use_llm \
  --model "gemini-2.0-flash-exp" \
  --output_format hierarchical_json

# Just section summaries
marker_single document.pdf --add-summaries

# Just breadcrumbs for database
marker_single document.pdf --enable-breadcrumbs
```

## Architecture

The enhancements follow Marker's processor pattern:
- Each feature is a separate processor
- Can be enabled/disabled independently
- Maintains backward compatibility

## Performance Impact

| Feature | Impact | Notes |
|---------|--------|-------|
| Breadcrumbs | Minimal | Adds metadata only |
| Summaries | 0.5-2s per section | LLM call latency |
| Hierarchy | Minimal | Structure transformation |
| LLM Selection | Varies | Depends on provider |

## Configuration

See `docs/feature_documentation.md` for detailed configuration options.

## Testing

Tests are organized in `tests/features/`:
- `test_section_summarizer.py` - Summary functionality
- `test_section_breadcrumbs.py` - Breadcrumb generation
- `test_hierarchical_document.py` - Hierarchy transformation

## Future Improvements

1. Async summary generation for better performance
2. Batch LLM calls for efficiency
3. Configurable summary prompts
4. Additional LLM provider support