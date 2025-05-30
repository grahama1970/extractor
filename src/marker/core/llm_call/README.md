# LLM Validation Loop

A flexible validation loop system for LLM calls with retry and plugin support. This package provides an extensible framework for validating LLM outputs with custom strategies while maintaining simple integration and backward compatibility.

## Features

- 🔄 **Intelligent Retry Mechanism**: Automatically retry failed validations with incremental feedback
- 🧩 **Plugin Architecture**: Easy to add custom validators without modifying core code
- 🔍 **Debug-First Design**: Comprehensive tracing and debugging capabilities
- ⚡ **Redis Caching**: Built-in caching support for improved performance
- 🎨 **Rich CLI Interface**: Beautiful command-line interface with typer and rich
- 📊 **Multiple Validators**: Table, image, math, code, citation, and general content validators
- 🔐 **Type Safety**: Full Pydantic model support for structured outputs

## Installation

```bash
pip install llm-validation-loop
```

Or install from source:

```bash
git clone https://github.com/VikParuchuri/marker.git
cd marker/marker/llm_call
pip install -e .
```

## Quick Start

### Basic Usage

```python
import litellm
from litellm import completion
from pydantic import BaseModel
from llm_validation.litellm_integration import completion_with_validation

# Define your response format
class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

# Make a validated LLM call
response = completion_with_validation(
    model="gemini/gemini-1.5-pro",
    messages=[
        {"role": "system", "content": "Extract the event information."},
        {"role": "user", "content": "Alice and Bob are going to a science fair on Friday."},
    ],
    response_format=CalendarEvent,
    validation_strategies=["field_presence(required_fields=['name', 'date', 'participants'])"],
    max_retries=3,
    enable_cache=True
)
```

### Using Custom Validators

```python
from llm_validation import validator, BaseValidator, ValidationResult

@validator("custom_validator")
class CustomValidator(BaseValidator):
    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold
    
    def validate(self, response, context):
        # Your validation logic here
        if some_condition:
            return ValidationResult(valid=True)
        else:
            return ValidationResult(
                valid=False,
                error="Validation failed",
                suggestions=["Try this instead"]
            )

# Use your custom validator
response = completion_with_validation(
    model="gemini/gemini-1.5-pro",
    messages=messages,
    response_format=MyModel,
    validation_strategies=["custom_validator(threshold=0.9)"]
)
```

### CLI Usage

```bash
# List available validators
llm-validate list-validators

# Validate with specific strategies
llm-validate validate "Summarize this text" \
    --validators length_check,required_fields \
    --max-retries 5 \
    --debug

# Add custom validator
llm-validate add-validator ./my_validators/citation_check.py

# Debug a validation run
llm-validate debug trace.json --show-errors-only
```

## Available Validators

### Base Validators
- `field_presence`: Validates required fields are present
- `length_check`: Validates field length constraints
- `format_check`: Validates field format using regex
- `type_check`: Validates field types
- `range_check`: Validates numeric ranges

### Specialized Validators
- **Table**: `table_structure`, `table_consistency`
- **Image**: `image_description`, `alt_text`
- **Math**: `latex_syntax`, `math_consistency`
- **Code**: `python_syntax`, `code_language`, `code_completeness`
- **Citation**: `citation_match`, `citation_format`, `citation_relevance`
- **General**: `content_quality`, `tone_consistency`, `json_structure`

## Architecture

The package follows a 3-layer architecture for maximum modularity:

```
llm_validation/
├── core/          # Core validation logic
├── cli/           # Command-line interface
└── validators/    # Built-in and custom validators
```

## Contributing

Contributions are welcome! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Links

- [Documentation](https://github.com/VikParuchuri/marker/tree/main/marker/llm_call)
- [GitHub Repository](https://github.com/VikParuchuri/marker)
- [Issue Tracker](https://github.com/VikParuchuri/marker/issues)