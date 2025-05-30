# LLM Validation Loop Documentation

Welcome to the LLM Validation Loop documentation. This library provides a flexible, extensible framework for validating LLM outputs with intelligent retry mechanisms and custom validation strategies.

## Overview

The LLM Validation Loop is designed to:
- Provide intelligent retry mechanisms for failed LLM validations
- Support custom validation strategies through a plugin architecture
- Offer comprehensive debugging and tracing capabilities
- Integrate seamlessly with existing LiteLLM workflows
- Cache responses for improved performance

## Key Features

- **🔄 Intelligent Retry**: Automatically retry failed validations with incremental feedback
- **🧩 Plugin Architecture**: Easy to add custom validators without modifying core code
- **🔍 Debug-First Design**: Comprehensive tracing and debugging capabilities
- **⚡ Redis Caching**: Built-in caching support for improved performance
- **🎨 Rich CLI**: Beautiful command-line interface with typer and rich
- **📊 20+ Validators**: Pre-built validators for tables, images, math, code, citations, and more
- **🔐 Type Safety**: Full Pydantic model support for structured outputs

## Documentation Structure

- [Getting Started](getting_started.md) - Installation and quick start guide
- [Core Concepts](core_concepts.md) - Understanding the validation framework
- [Validators](validators.md) - Built-in validators and how to create custom ones
- [CLI Reference](cli_reference.md) - Command-line interface documentation
- [API Reference](api_reference.md) - Complete API documentation
- [Examples](examples.md) - Code examples and use cases
- [Architecture](architecture.md) - System design and architecture
- [Contributing](contributing.md) - How to contribute to the project

## Quick Example

```python
from llm_validation import completion_with_validation
from pydantic import BaseModel

class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

response = completion_with_validation(
    model="gemini/gemini-1.5-pro",
    messages=[
        {"role": "system", "content": "Extract the event information."},
        {"role": "user", "content": "Alice and Bob are going to a science fair on Friday."},
    ],
    response_format=CalendarEvent,
    validation_strategies=["field_presence(required_fields=['name', 'date', 'participants'])"],
    max_retries=3
)
```

## Installation

```bash
pip install llm-validation-loop
```

## Support

- [GitHub Issues](https://github.com/VikParuchuri/marker/issues)
- [Discussions](https://github.com/VikParuchuri/marker/discussions)

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.