# Contributing to marker-llm-call

Thank you for your interest in contributing to marker-llm-call! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Git
- Redis (optional, for caching)
- uv (recommended) or pip

### Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/VikParuchuri/marker.git
   cd marker
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   # Using uv (recommended)
   uv pip install -e ".[dev]"
   
   # Or using pip
   pip install -e ".[dev]"
   ```

4. Set up pre-commit hooks:
   ```bash
   pre-commit install
   ```

## Code Style

We use the following tools to maintain code quality:

- **Black** for code formatting
- **isort** for import sorting
- **mypy** for type checking
- **pytest** for testing

Run all checks:
```bash
# Format code
black marker/llm_call
isort marker/llm_call

# Type checking
mypy marker/llm_call

# Run tests
pytest tests/
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_validators.py

# Run with coverage
pytest --cov=marker.llm_call --cov-report=html

# Run integration tests
pytest -m integration
```

### Writing Tests

1. Place tests in the `tests/` directory
2. Follow the naming convention: `test_*.py`
3. Use pytest fixtures for common setup
4. Mock external dependencies

Example test:
```python
import pytest
from marker.llm_call.validators import TableValidator
from marker.llm_call.base import ValidationResult

def test_table_validator_min_rows():
    """Test table validator minimum rows validation"""
    validator = TableValidator(min_rows=3)
    
    # Test invalid table (too few rows)
    invalid_table = {
        "headers": ["A", "B"],
        "rows": [["1", "2"]]
    }
    result = validator.validate(invalid_table)
    assert not result.valid
    assert "3 rows" in result.error
    
    # Test valid table
    valid_table = {
        "headers": ["A", "B"],
        "rows": [["1", "2"], ["3", "4"], ["5", "6"]]
    }
    result = validator.validate(valid_table)
    assert result.valid
```

## Adding a New Validator

1. Create a new file in `marker/llm_call/validators/`:
   ```python
   # marker/llm_call/validators/custom.py
   from typing import Any
   from marker.llm_call.base import ValidationStrategy, ValidationResult
   
   @validator("custom")
   class CustomValidator(ValidationStrategy):
       """Custom validator for specific use case"""
       
       def __init__(self, param1: str = "default"):
           self.param1 = param1
       
       def validate(self, content: Any) -> ValidationResult:
           # Implement validation logic
           if self._is_valid(content):
               return ValidationResult(valid=True)
           else:
               return ValidationResult(
                   valid=False,
                   error="Validation failed",
                   suggestions=["Try this instead"]
               )
       
       def _is_valid(self, content: Any) -> bool:
           # Custom validation logic
           return True
   ```

2. Add tests in `tests/validators/test_custom.py`:
   ```python
   import pytest
   from marker.llm_call.validators import CustomValidator
   
   def test_custom_validator():
       validator = CustomValidator(param1="test")
       result = validator.validate("test content")
       assert result.valid
   ```

3. Update documentation:
   - Add to validators list in `docs/api_reference.md`
   - Add usage example in `docs/examples.md`
   - Update CLI documentation if applicable

## Code Organization

### Directory Structure

```
marker/llm_call/
├── __init__.py         # Package exports
├── core/               # Core functionality
│   ├── __init__.py
│   ├── base.py        # Base classes and protocols
│   └── retry.py       # Retry logic
├── validators/         # Validator implementations
│   ├── __init__.py
│   ├── table.py
│   ├── image.py
│   └── ...
├── cli/               # CLI implementation
│   ├── __init__.py
│   └── main.py
└── litellm_integration.py  # LiteLLM service integration
```

### Import Guidelines

- Use absolute imports: `from marker.llm_call.base import ValidationResult`
- Expose public API in `__init__.py`
- Keep internal utilities private with underscore prefix

## Documentation

### Docstring Format

Use Google-style docstrings:

```python
def validate(self, content: Any) -> ValidationResult:
    """Validate the content according to strategy.
    
    Args:
        content: The content to validate. Type depends on validator.
    
    Returns:
        ValidationResult: Result containing validation status and details.
    
    Raises:
        ValueError: If content type is unsupported.
    
    Example:
        >>> validator = TableValidator(min_rows=2)
        >>> result = validator.validate(table_data)
        >>> print(result.valid)
    """
```

### Updating Documentation

1. Update relevant `.md` files in `docs/`
2. Include code examples where appropriate
3. Update the changelog for significant changes
4. Ensure all new features are documented

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Update documentation
7. Commit with clear message: `git commit -m "feat: add new validator"`
8. Push to your fork: `git push origin feature/your-feature`
9. Create a pull request

### Commit Message Format

Follow conventional commits:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation only
- `style:` Code style changes
- `refactor:` Code refactoring
- `test:` Test additions/changes
- `chore:` Build process or auxiliary tool changes

### PR Checklist

- [ ] Tests pass locally
- [ ] Code follows style guidelines
- [ ] Documentation is updated
- [ ] Commit messages are clear
- [ ] PR description explains changes

## Architecture Decisions

### Design Principles

1. **Modularity**: Keep validators independent
2. **Extensibility**: Easy to add new validators
3. **Type Safety**: Use type hints throughout
4. **Backward Compatibility**: Don't break existing APIs
5. **Performance**: Consider caching and async operations

### Adding Dependencies

1. Minimize external dependencies
2. Use optional dependencies when possible
3. Update `pyproject.toml` appropriately
4. Document why the dependency is needed

## Release Process

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create release PR
4. Tag release after merge: `git tag v1.2.3`
5. Push tag: `git push origin v1.2.3`

## Getting Help

- Check existing issues
- Join discussions
- Ask questions in pull requests
- Read the documentation

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Provide constructive feedback
- Focus on what is best for the community
- Show empathy towards others

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

## Recognition

Contributors are recognized in:
- The CONTRIBUTORS file
- Release notes
- Documentation credits

Thank you for contributing to marker-llm-call!