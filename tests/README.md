# Marker Test Suite

Organized test structure for the Marker project.

## Test Organization

### Core Tests
- `builders/` - Document builder tests
- `config/` - Configuration tests
- `converters/` - Converter tests
- `processors/` - Processor tests
- `providers/` - Provider tests
- `renderers/` - Renderer tests
- `schema/` - Schema tests
- `services/` - Service tests

### Feature Tests
- `features/` - Enhanced feature tests
  - `test_summarizer.py` - Section summarization
  - `test_section_breadcrumbs.py` - Breadcrumb functionality
  - `test_hierarchical_document.py` - Document hierarchy
  - `test_enhanced_table_*.py` - Enhanced table extraction
  - `test_litellm*.py` - LiteLLM service tests

### Integration Tests
- `integration/` - End-to-end tests
  - `test_e2e_workflow.py` - Full workflow tests
  - `test_regression_marker.py` - Regression tests

### Database Tests
- `database/` - Database-specific tests
  - `test_arangodb_import.py` - ArangoDB import
  - `test_arango_flattening.py` - Document flattening

## Running Tests

### Run all tests
```bash
pytest tests/
```

### Run specific test categories
```bash
# Core functionality
pytest tests/config/ tests/builders/ tests/converters/

# Enhanced features
pytest tests/features/

# Integration tests
pytest tests/integration/

# Database tests
pytest tests/database/
```

### Run with coverage
```bash
pytest tests/ --cov=marker --cov-report=html
```

## Test Guidelines

1. Keep tests focused and independent
2. Use fixtures for common setup
3. Mock external services (LLMs, databases)
4. Test both success and failure paths
5. Maintain clear test names and documentation