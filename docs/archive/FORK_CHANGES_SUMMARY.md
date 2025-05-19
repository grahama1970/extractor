# Fork Changes Summary

Complete list of changes made to the original Marker repository.

## New Features

### 1. Section Breadcrumbs
- **Files**: `marker/schema/blocks/sectionheader.py`
- **Purpose**: Enable hierarchical navigation for ArangoDB
- **Changes**: 
  - Added `section_hierarchy_titles` and `section_hierarchy_hashes`
  - Added hash generation for sections
  - Added breadcrumb building

### 2. LiteLLM Integration
- **Files**: `marker/services/litellm.py`
- **Purpose**: Unified interface for multiple LLM providers
- **Features**:
  - Support for OpenAI, Anthropic, Google, Vertex AI
  - Response caching
  - Retry logic
  - Cost tracking

### 3. Document Hierarchy
- **Files**: 
  - `marker/processors/enhanced/hierarchy_builder.py`
  - `marker/schema/enhanced_document.py`
- **Purpose**: Transform flat structure to nested sections
- **Features**:
  - Sections as parent containers
  - Preserved content order
  - Nested subsections

### 4. Section Summarization
- **Files**: `marker/processors/enhanced/summarizer.py`
- **Purpose**: Automatic LLM-generated summaries
- **Features**:
  - Per-section summaries
  - Document-level summary
  - Configurable prompts

### 5. Enhanced Table Extraction
- **Files**: 
  - `marker/processors/enhanced_camelot/processor.py`
  - `marker/processors/table_optimizer.py`
  - `marker/utils/table_quality_evaluator.py`
- **Purpose**: Improved table extraction with Camelot fallback
- **Features**:
  - Quality evaluation
  - Parameter optimization
  - Multi-page table merging

### 6. Image Description Generation
- **Files**: 
  - `marker/processors/llm/llm_image_description.py`
  - `marker/processors/llm/llm_image_description_async.py`
- **Purpose**: Generate alt text for images
- **Features**:
  - LLM-powered descriptions
  - Async batch processing
  - Progress tracking

### 7. ArangoDB Renderer
- **Files**: `marker/renderers/arangodb_json.py`
- **Purpose**: Export for graph database
- **Features**:
  - Flattened structure
  - Relationship metadata
  - Section breadcrumbs

### 8. Code Language Detection
- **Files**: `marker/services/utils/tree_sitter_utils.py`
- **Purpose**: Detect programming languages in code blocks
- **Features**:
  - 100+ language support
  - Confidence scoring
  - Syntax validation

## Modified Files

### Core Schema Changes
1. `marker/schema/blocks/sectionheader.py`:
   - Added breadcrumb support
   - Added hash generation
   - Added hierarchy tracking

2. `marker/schema/document.py`:
   - Added metadata fields
   - Added hierarchy support
   - Added summary storage

### Service Enhancements
1. `marker/services/__init__.py`:
   - Added LiteLLM service
   - Added service registry

2. `marker/processors/code.py`:
   - Integrated tree-sitter
   - Added language detection

### Configuration Changes
1. `marker/config/table.py`:
   - Simplified from 378 to 23 lines
   - Removed complex nested configs
   - Added simple presets

## New Directories

1. `marker/processors/enhanced/`:
   - Contains enhanced processors
   - Hierarchical structure
   - Summarization

2. `marker/services/utils/`:
   - Service utilities
   - Tree-sitter integration
   - Logging helpers

3. `marker/utils/`:
   - Table utilities
   - Embedding support
   - Text chunking

4. `tests/features/`:
   - Feature-specific tests
   - Mock implementations
   - Integration tests

## New CLI Flags

```bash
--add-summaries         # Enable section summarization
--enable-breadcrumbs    # Add section breadcrumbs  
--use-camelot          # Force Camelot for tables
--async-images         # Async image processing
--llm-service          # Specify LLM service
--model               # Specify model name
```

## Configuration Options

```json
{
    "use_llm": true,
    "llm_service": "marker.services.litellm.LiteLLMService",
    "llm_config": {
        "model": "vertex_ai/gemini-2.0-flash",
        "temperature": 0.3,
        "enable_cache": true
    },
    "table_config": {
        "use_camelot_fallback": true,
        "min_quality_score": 0.6,
        "optimize": false
    },
    "summaries": {
        "enabled": true,
        "max_section_length": 3000
    },
    "breadcrumbs": {
        "enabled": true,
        "include_hashes": true
    }
}
```

## Environment Variables

```bash
# LLM Configuration
LITELLM_MODEL="vertex_ai/gemini-2.0-flash"
GOOGLE_API_KEY="your-key"
VERTEX_PROJECT_ID="your-project"
ENABLE_CACHE=true

# Processing Options
MARKER_DEBUG=true
TORCH_DEVICE="cuda"
WORKERS=8

# Table Extraction
CAMELOT_FLAVOR="lattice"
TABLE_QUALITY_THRESHOLD=0.7
```

## Performance Improvements

1. **Async Processing**:
   - Image descriptions
   - LLM calls
   - Batch operations

2. **Caching**:
   - LLM response cache
   - Image processing cache
   - Table extraction cache

3. **Optimization**:
   - Table parameter tuning
   - Batch size optimization
   - GPU memory management

## Testing Enhancements

1. **Organized Structure**:
   ```
   tests/
   ├── features/      # New feature tests
   ├── integration/   # E2E tests
   ├── database/      # DB tests
   └── core/          # Original tests
   ```

2. **Mock Infrastructure**:
   - LLM response mocking
   - Image processing mocks
   - Performance benchmarks

## Dependencies Added

```toml
# pyproject.toml additions
litellm = "^0.35.0"
tree-sitter = "^0.20.0"
tree-sitter-languages = "^1.8.0"
camelot-py = {version = "^0.10.0", optional = true}
aiohttp = "^3.8.0"
```

## Backward Compatibility

- All enhancements are optional
- Default behavior unchanged
- Core API preserved
- No breaking changes

## Future Enhancements

1. **Planned Features**:
   - Vector search integration
   - Advanced entity extraction
   - Multi-modal embeddings

2. **Performance**:
   - Further async optimization
   - Distributed processing
   - Edge deployment