# Marker Fork Changelog

## [1.1.1] - 2026-02-04

### Assessment & Verification

Comprehensive assessment of the extractor project and pi-mono skills integration.

#### Task Verification (01_TASKS.md)
- **TASK-001 to TASK-004 (Blocking)**: All FIXED - code quality issues resolved
- **TASK-005 to TASK-008 (Sanity Functions)**: All IMPLEMENTED - 21 sanity() functions across all steps
- **TASK-009 to TASK-012 (Code Quality)**: All VERIFIED - issues fixed or false positives
- **TASK-013 to TASK-015 (Cleanup)**: All VERIFIED - cleanup completed
- **TASK-016 to TASK-026 (Preset Propagation)**: All COMPLETE - 14 files have preset_config

#### Skill Integration Verified
- `/extractor` skill: 10/10 format tests passing
- `/debug-pdf` skill: 11/11 sanity checks passing
- `/prompt-lab` skill: 8/8 sanity checks passing
- `/fixture-tricky` → extractor integration: Working (adversarial PDF handled correctly)

#### Documentation Updates
- Updated CONTEXT.md - removed stale `--sections-only` drift note (feature is implemented)
- Updated 01_TASKS.md - marked all tasks as verified with status notes
- Created PLAN_PIPELINE_IMPROVEMENTS.md - future improvement roadmap
- Created 02_PIPELINE_IMPROVEMENTS.md - orchestration task file

#### Test Results
- 516 tests collected
- 16/16 core tests passing
- All pipeline step imports verified
- All sanity() functions verified

## [1.1.0] - 2026-01-30

### Self-Healing Universal Extractor (NEW)
- `src/extractor/self_healing_extractor.py` - Universal extraction with automatic self-healing
  - Supports 12+ file types: PDF, DOCX, PPTX, XLSX, HTML, XML, Markdown, RST, EPUB, TXT, JSON, Images
  - Auto-detects file type and routes to appropriate provider
  - Self-healing loop: detect failure -> classify pattern -> apply fix -> retry
  - Memory integration for learning from successful fixes
  - CLI: `python -m extractor.self_healing_extractor file.pdf`

- `src/extractor/failure_detector.py` - Unified failure pattern detection
  - Universal patterns: file_not_found, empty_file, permission_denied, timeout, memory_error, encoding_error
  - PDF patterns: corrupted_pdf, password_protected, scanned_no_ocr, header_footer_bleed, multi_column
  - OOXML patterns: bad_zip, missing_content, ole_format
  - HTML/XML patterns: malformed_html, script_heavy, xml_syntax_error
  - Image patterns: corrupted_image, unsupported_format
  - Fix strategy registry with 24 strategies

### Pipeline Hardening Tools (NEW)
- `scripts/pipeline_hardening.py` - Bulk document analysis workflow
  - Analyze 1000+ documents in parallel
  - Pattern frequency reporting by file type
  - Interactive hardening loop
- `scripts/debug_pdf_local.py` - Local PDF pattern detection bridge

### Tests (NEW)
- `tests/test_self_healing_extractor.py` - 38 tests for self-healing extractor
- `tests/test_failure_detector.py` - 28 tests for failure detector

### PDF Extraction Improvements (s02_pymupdf_extractor.py)

#### New Block Types
- `PageHeader` - Content detected in top header region (top 8% of page)
- `PageFooter` - Content detected in bottom footer region (bottom 10% of page)
- `Footnote` - Footnote content detected at bottom of page

#### Bug Fixes
- **header_footer_bleed**: Position-based detection + pattern matching for headers/footers
- **curly_quotes**: Enhanced `_normalize_text()` with Windows-1252 + Unicode quote mapping
- **invisible_chars**: Zero-width characters and directional formatting removed
- **footnotes_inline**: `_detect_footnote()` with position/font/marker detection
- **multi_column**: Column boundary detection + reading order correction
- **sparse_content_slides**: Slide deck detection via aspect ratio + text density
- **corrupted_file**: Robust error handling for FileDataError/EmptyFileError
- **scanned_no_ocr**: `_detect_scanned_pdf()` with text/image ratio analysis

### Header/Footer Verification (s03_suspicious_headers.py)
- Added `HEADER_FOOTER_PATTERNS` and `HEADER_FOOTER_CONTENT_EXCEPTIONS`
- New `_verify_page_header_footer()` for LLM verification of header/footer blocks
- `header_footer_stats` tracking in output JSON

### HTML Provider - SPA Support Fix
- **Bug Fixed**: HTMLProvider was ignoring rolling windows from fetcher
  - Root cause: Code logged rolling windows existed but never used them
  - For JS SPAs like MITRE ATT&CK, raw HTML is mostly JavaScript templates
  - The 300-400KB of actual content was in rolling windows - being discarded
- **Fix**: `_blocks_from_rolling_windows()` method added to `html.py`
  - Uses rolling windows when >1KB of pre-extracted content available
  - Deduplicates overlapping paragraph text
  - Creates HEADING/PARAGRAPH blocks from Playwright-rendered content
  - Falls back to BeautifulSoup only when rolling windows fail
- **Impact**: 245 previously empty attack.mitre.org URLs now extract correctly

### Fetcher Bridge - Compose-able Skill Support
- **Bug Fixed**: Rolling windows lost when skills composed (/fetcher → /extractor)
  - Root cause: ensure_local_source() only returned FetcherDownload for URLs
  - When extractor received a file path (after fetcher ran), no rolling windows loaded
- **Fix**: `_discover_rolling_windows()` in `fetcher_bridge.py`
  - Looks for sibling JSONL files when given local paths
  - Supports patterns: `{stem}_rolling_windows.jsonl`, `{stem}.rolling_windows.jsonl`, etc.
  - Also checks `{stem}_metadata.json` for rolling_windows_path
- **Impact**: Compose-able skill workflow now preserves rolling windows

### Test Fixtures
- `test_output/fixtures/test_combined_stress.pdf` (all patterns)
- Individual test fixtures for each extraction pattern

---

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