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

### 5. ArangoDB Integration
- Added `arangodb_json.py` in `marker/renderers/` for graph database output 
- Created flattened, database-ready JSON representation of documents
- Included section context with each content object for better connectivity
- Added metadata tracking for document structure statistics
- Added ArangoDB setup utilities in `marker/utils/arango_setup.py`
- Implemented vector search capabilities for document similarity
- Added integration with LLM validation system for AQL query generation
- Created comprehensive demo scripts and integration guides
- Added inter-module communication capabilities with conversation threading

### 6. LLM Validation Framework
- Created standalone `marker/llm_call` module for LLM output validation
- Implemented core validation loop with retry mechanisms
- Added validators for various content types (code, math, tables, etc.)
- Created CLI tools for testing and verification
- Added documentation and examples for extension

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
   - `examples/simple/arangodb_operations_debug.py`: Testing ArangoDB operations
   - `examples/simple/arango_vector_index_debug.py`: Vector search demonstration
   - `scripts/demos/arangodb_integration_demo.py`: Comprehensive integration demo
   - `examples/marker_arangodb_communication_demo.py`: Inter-module communication

6. LLM Validation:
   - `corpus_validator_cli.py`: CLI for corpus validation
   - `test_validators_simple.py`: Simple validator tests
   - `test_arangodb_integration_verification.py`: Integration verification

7. Other Utilities:
   - `examples/markdown_extractor.py`: Markdown content extraction example
   - `examples/table_extractor.py`: Table data extraction example

## Documentation

Added comprehensive documentation for all new features:

1. Integration Guides:
   - `docs/integration/arangodb_integration_guide.md`: Basic integration steps
   - `docs/integration/arangodb_integration_guide_uv.md`: Using UV package manager
   - `docs/integration/INTEGRATION_SUMMARY.md`: Architecture overview
   - `docs/integration/ARANGODB_INTEGRATION.md`: Detailed feature guide

2. API Documentation:
   - `docs/api/MARKER_ARANGODB_API.md`: ArangoDB API reference

3. Task Reports:
   - `docs/reports/032_task_1_arangodb_renderer.md`: Renderer implementation
   - `docs/reports/032_task_3_arangodb_import.md`: Import functionality
   - `docs/reports/032_task_3_arangodb_import_update.md`: Import enhancements

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
   - Enhanced services with ArangoDB integration support

## Testing

Added tests for all new features:
   - `tests/services/test_litellm_service.py`: LiteLLM service tests
   - `tests/renderers/test_section_breadcrumbs.py`: Section breadcrumbs tests
   - `tests/services/utils/test_litellm_cache.py`: Cache functionality tests
   - `tests/database/test_arangodb_import.py`: ArangoDB import tests
   - `tests/database/test_arango_flattening.py`: JSON flattening tests
   - `tests/arangodb/test_arangodb_integration_verification.py`: Integration tests
   - `tests/arangodb/test_arangodb_quick.py`: Quick ArangoDB tests
   - `tests/arangodb/test_arangodb_renderer.py`: Renderer tests
   - LiteLLM conversion tests in the tests/services/litellm directory