# Marker Fork Changelog

## Added Features

### 1. Tree-Sitter Language Detection
- Added `tree_sitter_utils.py` in `marker/services/utils/` with comprehensive language detection capabilities
- Enhanced `marker/processors/code.py` to use tree-sitter for accurate code language detection
- Support for 100+ programming languages with detailed metadata extraction
- Added code block language detection heuristics as fallback when tree-sitter is unavailable

### 2. LiteLLM Integration
- Added `litellm.py` in `marker/services/` providing a unified interface to multiple LLM providers
- Added support for provider-specific API key loading from environment variables
- Added caching capabilities in `marker/services/utils/litellm_cache.py` to reduce API costs
- Various utility functions for handling JSON responses and logging in `marker/services/utils/`

### 3. Asynchronous Image Description Generation
- Added async version of image description processor (`llm_image_description_async.py`)
- Implemented batched processing with configurable batch sizes
- Added semaphore-based concurrency control to limit simultaneous API calls
- Enhanced error handling and processing time tracking

### 4. Section Hierarchy and Breadcrumbs
- Enhanced `SectionHeader` block implementation in `marker/schema/blocks/sectionheader.py`
- Added `get_section_breadcrumbs()` method to `Document` class
- Implemented breadcrumb generation for HTML output with data attributes
- Added section hierarchy metadata to support navigation and context

### 5. ArangoDB JSON Renderer
- Added `arangodb_json.py` in `marker/renderers/` for graph database output 
- Created flattened, database-ready JSON representation of documents
- Included section context with each content object for better connectivity
- Added metadata tracking for document structure statistics

## Examples and Debug Scripts

Added several example and debug scripts to demonstrate the new features:

1. Enhanced Features:
   - `examples/enhanced_features.py`: Combined example of all new features
   - `examples/simple/enhanced_features_debug.py`: Simplified debugging tool

2. Tree-Sitter Language Detection:
   - `examples/simple/code_language_detection_debug.py`: Tree-sitter language detection demo

3. LiteLLM Integration:
   - `examples/initialize_litellm_cache.py`: LiteLLM cache initialization example
   - `examples/use_litellm_service.py`: LiteLLM service usage example
   - `examples/simple/litellm_cache_debug.py`: LiteLLM caching debug tool

4. Section Hierarchy:
   - `examples/section_hierarchy.py`: Section hierarchy and breadcrumbs example
   - `examples/simple/section_hierarchy_debug.py`: Section structure debugging tool

5. ArangoDB Integration:
   - `examples/arangodb_import.py`: ArangoDB import example
   - `examples/simple/arangodb_json_debug.py`: ArangoDB JSON format debugging tool

6. Other Utilities:
   - `examples/markdown_extractor.py`: Markdown content extraction example
   - `examples/table_extractor.py`: Table data extraction example

## Changed

1. Updated several processors to support the new features:
   - Enhanced sectionheader.py with breadcrumb generation
   - Modified document.py to track section hierarchy context
   - Updated code.py to integrate tree-sitter language detection

2. Improved renderers:
   - Added section metadata support to markdown.py
   - Added new arangodb_json.py renderer

3. Service Enhancements:
   - Updated services/__init__.py to include LiteLLM service
   - Added utils directory with support libraries

## Testing

Added tests for all new features:
   - `tests/services/test_litellm_service.py`: LiteLLM service tests
   - `tests/renderers/test_section_breadcrumbs.py`: Section breadcrumbs tests
   - `tests/services/utils/test_litellm_cache.py`: Cache functionality tests
   - LiteLLM conversion tests in the tests/services/litellm directory