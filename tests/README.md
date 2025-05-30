# Marker Tests

This directory contains all tests for the Marker project. The test structure mirrors the source code structure in `src/marker/` for easy navigation and maintenance.

## Test Organization

The test directory structure mirrors the `src/marker/` source directory:

```
tests/
├── cli/                # Tests for CLI functionality (mirrors src/marker/cli/)
├── core/               # Core functionality tests (mirrors src/marker/core/)
│   ├── arangodb/       # ArangoDB integration tests
│   │   ├── database/   # Database-specific tests
│   │   └── validators/ # Validator tests
│   ├── builders/       # Document builder tests
│   ├── config/         # Configuration tests
│   ├── converters/     # File converter tests
│   ├── llm_call/       # LLM call module tests
│   │   └── validators/ # LLM validator tests
│   ├── processors/     # Document processor tests
│   │   ├── code/       # Code processor tests
│   │   └── llm/        # LLM processor tests
│   ├── providers/      # Document provider tests
│   │   └── pdf/        # PDF-specific tests
│   ├── renderers/      # Output renderer tests
│   ├── schema/         # Document schema tests
│   │   └── groups/     # Schema group tests
│   └── services/       # Service tests
│       ├── litellm/    # LiteLLM service tests
│       └── utils/      # Service utility tests
├── mcp/                # MCP server tests (mirrors src/marker/mcp/)
├── features/           # Feature integration tests
├── integration/        # End-to-end integration tests
│   └── arangodb/       # ArangoDB integration tests
├── metadata/           # Metadata-specific tests
├── package/            # Package build tests
└── verification/       # Verification and validation tests
```

## Running Tests

### Prerequisites

1. Activate the virtual environment:
   ```bash
   cd /home/graham/workspace/experiments/marker
   source .venv/bin/activate
   ```

2. Ensure dependencies are installed:
   ```bash
   uv sync --active
   ```

### Running All Tests

To run the complete test suite:

```bash
# Using uv (recommended)
uv run pytest tests/

# Run with coverage report
uv run pytest tests/ --cov=src/marker --cov-report=html

# Run with verbose output
uv run pytest tests/ -v

# Run with parallel execution (faster)
uv run pytest tests/ -n auto

# Or using the provided test script
./scripts/run_tests.sh
```

### Running Specific Test Categories

```bash
# Run only unit tests (exclude integration)
uv run pytest tests/ -k "not integration"

# Run only integration tests
uv run pytest tests/integration/

# Run tests for a specific module
uv run pytest tests/core/processors/
uv run pytest tests/core/arangodb/
uv run pytest tests/core/llm_call/

# Run tests for a specific feature
uv run pytest tests/core/processors/test_table_processor.py
uv run pytest tests/core/renderers/test_json_renderer.py
```

### Running Individual Test Files

```bash
# Run a specific test file
pytest tests/processors/test_table_processor.py

# Run a specific test function
pytest tests/processors/test_table_processor.py::test_table_extraction

# Run with print statements visible
pytest tests/processors/test_table_processor.py -s
```

### Test Markers

Tests are marked with different categories:

```bash
# Run only fast tests
pytest tests/ -m "not slow"

# Run only tests that require GPU
pytest tests/ -m "gpu"

# Run only tests that require external services
pytest tests/ -m "external"
```

### Debugging Failed Tests

```bash
# Stop at first failure
pytest tests/ -x

# Drop into debugger on failure
pytest tests/ --pdb

# Show local variables on failure
pytest tests/ -l

# Maximum verbosity for debugging
pytest tests/ -vvv
```

## Test Guidelines

### Writing New Tests

1. **Mirror Source Structure**: Place test files in the same relative location as the source file
   - Source: `src/marker/core/processors/table.py`
   - Test: `tests/core/processors/test_table.py`

2. **Naming Convention**: 
   - Test files: `test_<module_name>.py`
   - Test functions: `test_<functionality>_<scenario>()`

3. **Use Real Data**: Always test with actual data, never mock core functionality

4. **Test Coverage**: Each module should have:
   - Unit tests for individual functions
   - Integration tests for module interactions
   - Edge case tests
   - Error handling tests

### Test Data

Test data files are located in:
- `data/input_test/` - Input test files (PDFs, images, etc.)
- `tests/fixtures/` - Test fixtures and sample data

### Continuous Integration

Before pushing changes:

```bash
# Run full test suite
pytest tests/

# Check code coverage
pytest tests/ --cov=marker --cov-report=term-missing

# Run linting
ruff check marker/ tests/

# Run type checking
mypy marker/
```

## Test Reports

Test reports are automatically generated after full test suite runs and saved in `docs/reports/` with timestamp-based filenames.

To generate a test report manually:

```bash
pytest tests/ --junit-xml=test-results.xml
python scripts/generate_test_report.py test-results.xml
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure you're in the project root and virtual environment is activated
2. **Missing Dependencies**: Run `uv sync --active` to install all dependencies
3. **GPU Tests Failing**: Some tests require CUDA; skip with `-m "not gpu"`
4. **Slow Tests**: Use `-n auto` for parallel execution or `-m "not slow"` to skip slow tests

### Getting Help

For test-related issues:
1. Check test output for specific error messages
2. Run with `-vvv` for maximum verbosity
3. Check `docs/troubleshooting.md` for common solutions
4. Open an issue with test logs if problem persists

## Test Cleanup Summary

The following tests were archived to `archive/old_tests/` as duplicates or iterations:

### Language Detection Tests (Archived)
- Kept: `test_ts_language_detection.py`, `test_comprehensive_language_detection.py`
- Archived: Older iterations and simple versions

### Code Detection Tests (Archived)
- Kept: `test_enhanced_code_processor.py`
- Archived: Simple and older versions

### Integration Tests (Archived)
- Kept: v2 versions of extraction tests
- Archived: v1 versions and duplicates

All archived tests are preserved in `archive/old_tests/` with their original structure for reference.