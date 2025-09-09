# Extractor Deprecation Analysis

## Overview
This document provides a comprehensive analysis of files and directories that can be deprecated in the Extractor project. The analysis is based on:
- Current pipeline usage (poc_simplified pipeline)
- Import dependencies
- Test coverage
- File duplication and obsolescence

## Active Components (DO NOT DELETE)

### Core Pipeline (`src/extractor/pipeline/poc_simplified/pipeline/`)
The following files are actively used in the current pipeline:
- `00_run_pipeline.py` - Main orchestrator
- `01_annotation_processor.py` - Annotation extraction
- `02_marker_extractor.py` - Core Marker integration
- `03_suspicious_headers.py` - Header detection
- `04_section_builder.py` - Section construction
- `05_table_extractor.py` - Table extraction
- `06_figure_extractor.py` - Figure/image extraction
- `07_reflow_section.py` - LLM-based reflow
- `08_lean4_theorem_prover.py` - Formal verification
- `09_section_summarizer.py` - Summary generation
- `10_arangodb_exporter.py` - Database export
- `11_arango_create_graph.py` - Graph creation
- `14_report_generator.py` - Report generation

### Core Components (`src/extractor/core/`)
- `config/` - Configuration files
- `processors/` - Active processors (except deprecated subdirectory)
- `providers/` - Document providers
- `renderers/` - Output renderers
- `schema/` - Data schemas
- `services/` - Service integrations (LiteLLM, etc.)
- `utils/` - Utility functions

### CLI and MCP Servers
- `src/extractor/cli/` - Command-line interface
- `src/extractor/servers/` - MCP server implementations

## Deprecated Components (CAN BE DELETED)

### 1. Entire Deprecated Directory
**Path:** `src/extractor/core/deprecated/`
**Reason:** Explicitly marked as deprecated, containing 50+ obsolete files
**Action:** Delete entire directory

### 2. Old Pipeline Implementations
**Path:** `src/extractor/pipeline/poc_simplified/deprecated/`
**Contents:**
- Old marker extractors
- Broken table extractors
- Duplicate stage implementations
- Old debugging scripts
**Action:** Delete entire directory

### 3. Temporary Files
**Path:** `tmp/`
**Reason:** Contains 100+ temporary test files, debug scripts, and experiments
**Action:** Move critical lessons/documentation to proper locations, then delete

### 4. Obsolete Tests
**Path:** `tests/`
**Files to remove:**
- `test_claude_*.py` (20+ files) - Claude-specific tests now handled by MCP
- `test_marker_*.py` - Old marker tests
- `test_ai_image_*.py` - Obsolete image tests
- `test_*_fix.py` - Temporary fix validation tests
**Action:** Keep only core integration tests and pytest fixtures

### 5. Proof of Concept Directories
**Paths:**
- `proof_of_concept/` - Old POC implementations
- `src/extractor/pipeline/poc_simplified/proof_of_concept/`
- `src/extractor/pipeline/poc_simplified/old_*` directories
**Action:** Extract any valuable documentation, then delete

### 6. Archive Directories
**Paths:**
- `archive/` - Old documentation and configs
- `.archive/` - Hidden archive
- `_archive/` - Another archive variant
**Action:** Review for critical documentation, then delete

### 7. Duplicate Result Directories
**Paths:**
- `pipeline_output/`
- `pipeline_output_unified/`
- `pipeline_results/`
- `src/extractor/pipeline/poc_simplified/results/`
- `src/extractor/pipeline/poc_simplified/old_results/`
**Action:** Consolidate to single output directory, delete others

### 8. Old Documentation Files (Root Level)
**Files:**
- Various `*_SUMMARY.md`, `*_REPORT.md`, `*_FIX.md` files
- Old analysis and implementation docs
**Action:** Move valuable content to `docs/`, delete originals

### 9. Unused Dependencies
**In pyproject.toml:**
- `camelot-py` - Commented out, using pdfplumber instead
- `cv2-tools` - Only needed for camelot
- `weasyprint` - Commented out, not used
**Action:** Remove from dependencies

### 10. Old Scripts and Examples
**Paths:**
- `scripts/` - Contains many obsolete analysis scripts
- `examples/` - Contains outdated examples
**Action:** Keep only actively maintained examples

## Migration Plan

### Phase 1: Documentation Preservation (1 day)
1. Review all documentation in deprecated directories
2. Extract valuable insights and move to `docs/`
3. Update README.md with current architecture

### Phase 2: Test Cleanup (1 day)
1. Identify core tests that match current pipeline
2. Remove all Claude-specific and fix-specific tests
3. Update pytest configuration

### Phase 3: Directory Cleanup (1 day)
1. Delete `src/extractor/core/deprecated/`
2. Delete all POC and archive directories
3. Consolidate output directories

### Phase 4: Dependency Cleanup (0.5 day)
1. Remove unused dependencies from pyproject.toml
2. Run tests to ensure nothing breaks
3. Update requirements

### Phase 5: Final Cleanup (0.5 day)
1. Remove temporary files from `tmp/`
2. Clean root directory of old reports
3. Update .gitignore

## Expected Benefits

1. **Reduced Complexity:** ~70% reduction in file count
2. **Clearer Structure:** Obvious path for new contributors
3. **Faster Development:** Less confusion about which components are active
4. **Smaller Repository:** Significant reduction in repository size
5. **Better Maintenance:** Easier to identify and update active components

## Risks and Mitigations

1. **Risk:** Losing important implementation details
   **Mitigation:** Thorough documentation review before deletion

2. **Risk:** Breaking hidden dependencies
   **Mitigation:** Run full test suite after each phase

3. **Risk:** Losing experimental code that might be useful
   **Mitigation:** Create a final archive branch before deletion

## Recommended Order of Execution

1. Start with `src/extractor/core/deprecated/` - lowest risk
2. Clean up test directories - medium risk
3. Remove POC directories - medium risk
4. Clean tmp/ - requires careful review
5. Final root cleanup - highest visibility

## Verification Steps

After each phase:
1. Run the pipeline with test PDFs
2. Execute pytest suite
3. Verify MCP server functionality
4. Check CLI commands still work

## Summary

This cleanup will remove approximately:
- 200+ deprecated Python files
- 50+ obsolete test files
- 100+ temporary/debug scripts
- Multiple duplicate directories

The result will be a cleaner, more maintainable codebase focused on the active POC simplified pipeline implementation.