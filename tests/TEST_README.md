# Extractor Tests - Granger Ecosystem

## Overview

This test suite focuses on verifying core functionality needed for the extractor module to work within the Granger ecosystem pipeline: **SPARTA → Extractor → ArangoDB → Unsloth**

## Test Philosophy

- **Minimal & Essential**: Only test core functionality, avoiding technical debt
- **Real Interactions**: No mocks - tests use real modules (per CLAUDE.md)
- **Granger-Focused**: Tests verify integration points with the ecosystem

## Test Structure

```
tests/
├── conftest.py                    # Test configuration
├── test_basic_functionality.py    # Basic module structure tests
├── test_core_functionality.py     # Core extractor capabilities
├── test_honeypot.py              # Framework integrity verification
├── verify_basic_setup.py         # Setup verification (no imports)
├── run_core_tests.py             # Simple test runner
└── integration/
    └── test_granger_pipeline.py  # Pipeline integration tests
```

## Core Tests

### 1. Basic Functionality (`test_basic_functionality.py`)
- Python version check
- Project structure verification
- Module import validation

### 2. Core Functionality (`test_core_functionality.py`)
- Document extraction capabilities
- Multi-format support (PDF, DOCX, PPTX, XML)
- ArangoDB output rendering
- Table extraction methods
- Pipeline readiness

### 3. Integration Tests (`integration/test_granger_pipeline.py`)
- PDF to JSON conversion
- ArangoDB output format
- CLI interface
- MCP server tools
- Granger hub compatibility

### 4. Honeypot Tests (`test_honeypot.py`)
- Designed to fail
- Verifies test framework integrity
- Ensures no mocking/faking

## Running Tests

### Quick Verification
```bash
# Verify basic setup (no dependencies needed)
python tests/verify_basic_setup.py

# Run core tests without pytest
python tests/run_core_tests.py
```

### With pytest (if available)
```bash
# Run all tests
pytest tests/ -v

# Run only integration tests
pytest tests/integration/ -v -m integration

# Run with timing info
pytest tests/ -v --durations=0
```

## What We Test

✅ **Essential for Granger Pipeline:**
- Can accept documents from SPARTA
- Can extract from multiple formats
- Can output to ArangoDB/JSON
- Has MCP server for hub integration
- Has CLI for command-line usage

❌ **What We Don't Test:**
- Implementation details
- Every edge case
- Performance benchmarks
- UI/visualization features
- Optional features

## Integration Points

The extractor module integrates with:
1. **SPARTA** - Receives documents for processing
2. **ArangoDB** - Outputs structured data for storage
3. **Granger Hub** - Communication via MCP server
4. **Unsloth** - Downstream processing of extracted data

## Maintenance

When adding new tests:
1. Ask: "Is this essential for Granger pipeline?"
2. Keep tests simple and readable
3. Avoid testing implementation details
4. Use real modules, not mocks
5. Document why the test is needed

## Known Issues

- Some imports may fail due to syntax errors in dependencies
- Use `verify_basic_setup.py` for structure verification without imports
- The venv Python path must be used for proper module resolution