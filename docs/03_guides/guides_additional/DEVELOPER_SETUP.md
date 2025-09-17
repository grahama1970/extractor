# Developer Setup Guide

This guide helps you set up a development environment for contributing to Marker.

## Prerequisites

- Python 3.9+
- Git
- CUDA toolkit (optional, for GPU support)
- 8GB+ RAM (16GB recommended)

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/USERNAME/marker.git
cd marker
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Install in development mode
pip install -e ".[dev]"

# Install all extras
pip install -e ".[dev,cli,api]"
```

### 4. Download Models

```bash
# Download required models
marker download-models

# Or specific models
marker download-models --model surya_det --model surya_rec
```

### 5. Set Up Pre-commit Hooks

```bash
pre-commit install
```

## Configuration

### Environment Variables

Create `.env` file in project root:

```env
# Required
PYTHONPATH=/path/to/marker

# Optional API Keys
OPENAI_API_KEY=your-key
ANTHROPIC_API_KEY=your-key
GEMINI_API_KEY=your-key

# Optional Paths
MARKER_MODEL_PATH=/custom/model/path
MARKER_CACHE_DIR=/custom/cache/path

# Development
MARKER_DEBUG=1
MARKER_DEVICE=cuda
```

### IDE Setup

#### VS Code

`.vscode/settings.json`:
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false
}
```

#### PyCharm

1. Set Python interpreter to `.venv/bin/python`
2. Mark `marker` directory as Sources Root
3. Enable pytest as test runner
4. Configure code style to use Black

## Running Tests

### Unit Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/converters/test_pdf_converter.py

# Run with coverage
pytest --cov=marker --cov-report=html

# Run specific test
pytest -k test_table_extraction
```

### Integration Tests

```bash
# Run integration tests
pytest tests/integration/

# Run with real PDFs
pytest tests/integration/test_real_pdfs.py --real-pdfs
```

### Performance Tests

```bash
# Run benchmarks
pytest benchmarks/

# Profile specific operation
python -m cProfile -o profile.stats marker/cli.py convert test.pdf
```

## Development Workflow

### 1. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

Follow the coding standards:
- Use Black for formatting
- Add type hints
- Write docstrings
- Add tests

### 3. Test Changes

```bash
# Run linting
flake8 marker/
mypy marker/

# Run tests
pytest tests/

# Test CLI
marker convert test.pdf --debug
```

### 4. Commit Changes

```bash
git add .
git commit -m "feat: add your feature description"
```

Follow commit message convention:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `test:` Tests
- `refactor:` Code refactoring
- `chore:` Maintenance

### 5. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Debugging

### Enable Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or via environment
export MARKER_DEBUG=1
```

### Use VS Code Debugger

`.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug Marker CLI",
      "type": "python",
      "request": "launch",
      "module": "marker.cli",
      "args": ["convert", "test.pdf"],
      "console": "integratedTerminal"
    }
  ]
}
```

### Memory Profiling

```python
from memory_profiler import profile

@profile
def convert_pdf(filepath):
    converter = PdfConverter()
    return converter(filepath)
```

## Common Development Tasks

### Adding a New Processor

1. Create processor file:
```python
# marker/processors/my_processor.py
from marker.processors.base import BaseProcessor

class MyProcessor(BaseProcessor):
    def __init__(self, config=None):
        super().__init__(config)
    
    def __call__(self, document):
        # Process document
        return document
```

2. Add to processor registry:
```python
# marker/processors/__init__.py
from .my_processor import MyProcessor

PROCESSORS = {
    'my_processor': MyProcessor,
    # ...
}
```

3. Add tests:
```python
# tests/processors/test_my_processor.py
def test_my_processor():
    processor = MyProcessor()
    document = create_test_document()
    result = processor(document)
    assert result is not None
```

### Adding a New Model

1. Create model wrapper:
```python
# marker/models/my_model.py
class MyModel:
    def __init__(self, model_path):
        self.model = load_model(model_path)
    
    def predict(self, input_data):
        return self.model(input_data)
```

2. Add to model registry:
```python
# marker/models/registry.py
MODELS = {
    'my_model': MyModel,
    # ...
}
```

### Adding CLI Command

1. Create command:
```python
# marker/cli/commands/my_command.py
import click

@click.command()
@click.argument('input_file')
def my_command(input_file):
    """Description of command."""
    # Implementation
```

2. Register command:
```python
# marker/cli/__init__.py
from .commands.my_command import my_command

cli.add_command(my_command)
```

## Troubleshooting Development

### Import Errors

```bash
# Ensure PYTHONPATH is set
export PYTHONPATH=/path/to/marker:$PYTHONPATH

# Or use development install
pip install -e .
```

### Model Loading Issues

```bash
# Clear model cache
rm -rf ~/.cache/marker/models/

# Re-download models
marker download-models --force
```

### GPU Memory Issues

```python
# Clear GPU cache
import torch
torch.cuda.empty_cache()

# Monitor GPU usage
nvidia-smi -l 1
```

## Resources

- [Contributing Guide](../CONTRIBUTING.md)
- [Coding Standards](../CODING_STANDARDS.md)
- [Architecture Overview](../ARCHITECTURE.md)
- [API Documentation](../api/)