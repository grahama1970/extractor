# Tests

## Quick Start

```bash
# Run all tests
pytest

# With coverage
pytest --cov

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

## Test Structure

Tests mirror the source code structure for easy navigation.

## Running Specific Tests

```bash
# Run specific test file
pytest tests/test_example.py

# Run specific test
pytest tests/test_example.py::test_function_name

# Run tests matching pattern
pytest -k "pattern"
```

## Before Committing

```bash
# Run all tests with strict mode
pytest --strict-markers -v

# Check coverage
pytest --cov --cov-report=html
```
