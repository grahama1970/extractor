# Project Reorganization Plan

## Overview
This document outlines the reorganization plan for the extractor project to clean up obsolete files, organize scattered scripts, and improve project structure.

## Current Issues
1. **Project Root Clutter**: 22 Python scripts and large JSON files in the root directory
2. **Duplicate Files**: Multiple versions of similar functionality
3. **Scattered Test Results**: Test outputs spread across multiple directories
4. **Obsolete POCs**: Proof of concept files that have been superseded

## Reorganization Plan

### 1. Project Root Cleanup

#### Files to Move to `scripts/debug/`:
- `debug_and_fix_extractor.py`
- `diagnose_extractor_import.py`
- `fix_surya_dependencies.py`

#### Files to Move to `examples/`:
- `extractor_usage_function.py`
- `demonstrate_current_state.py`
- `minimal_pdf_json_example.py`

#### Files to Move to `scripts/comparison/`:
- `marker_extractor_comparison.py`
- `test_original_marker.py`
- `use_original_marker_simple.py`
- `original_marker_isolated.py`

#### Files to Move to `docs/guides/`:
- `standalone_extractor_setup.py` (convert to markdown guide)

#### Files to Move to `src/granger_common/`:
- `granger_security_middleware_simple.py`

#### Files to DEPRECATE (move to `deprecated/`):
- `MINIMAL_PDF_JSON_EXAMPLE.py` (duplicate)
- `pdf_to_json_working_poc.py` (superseded)
- `simple_pdf_to_json_poc.py` (superseded)
- `final_usage_test.py` (redundant)
- `final_working_test.py` (redundant)
- `standalone_final_test.py` (redundant)
- `test_simple_pdf_extraction.py` (redundant)

#### Files to Remove:
- `unified_output.json` (1.1MB - old output file)
- `debug_info.json` (old debug output)

### 2. Test Organization

#### `test_reports/` Directory:
- Keep as historical archive
- Consider moving to `docs/test_history/` if not actively used

#### `test_results/` Directory:
Structure should be:
```
test_results/
├── archive/           # Old test results
│   └── 2024/         # By year
└── current/          # Latest test results only
```

Move all existing results to `archive/2024/`

#### `tests/` Directory:
Obsolete tests to deprecate:
- `test_honeypot.py` (if not relevant)
- `debug_imports.py` (debug script, not a test)
- `verify_basic_setup.py` (one-time verification)
- `verify_with_skepticism.py` (unclear purpose)

### 3. New Directory Structure
```
extractor/
├── src/                    # Source code
├── tests/                  # Active tests only
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── examples/               # Usage examples
├── scripts/               # Utility scripts
│   ├── debug/             # Debugging tools
│   ├── comparison/        # Comparison tools
│   └── analysis/          # Analysis scripts
├── docs/                  # Documentation
│   ├── guides/            # Setup and usage guides
│   └── test_history/      # Historical test reports
├── deprecated/            # Deprecated files (temporary)
├── data/                  # Test data and resources
└── [config files]         # pyproject.toml, etc.
```

### 4. Implementation Steps

1. **Create new directories**:
   ```bash
   mkdir -p scripts/{debug,comparison,analysis}
   mkdir -p examples
   mkdir -p docs/{guides,test_history}
   mkdir -p deprecated
   mkdir -p test_results/{archive/2024,current}
   ```

2. **Move files to appropriate locations**

3. **Update imports in any files that reference moved scripts**

4. **Update .gitignore to exclude**:
   - `deprecated/`
   - Large output files
   - Temporary test results

5. **Clean up deprecated directory after 30 days**

### 5. Additional Recommendations

1. **Establish naming conventions**:
   - Examples: `example_*.py`
   - Debug scripts: `debug_*.py`
   - Analysis scripts: `analyze_*.py`

2. **Add README files**:
   - In each major directory explaining its purpose
   - In examples/ with usage instructions

3. **Consider using pytest fixtures** instead of standalone test scripts

4. **Document the purpose** of any script that remains in the project

## Timeline
- Phase 1 (Immediate): Move files, create directories
- Phase 2 (1 week): Update documentation and imports
- Phase 3 (30 days): Remove deprecated directory