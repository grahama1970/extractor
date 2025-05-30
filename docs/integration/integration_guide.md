# LLM Validation Integration Guide

## Overview

The `llm_call` module provides a flexible validation system that can be integrated into any project, including the ArangoDB project.

## Architecture

```
Your Project (e.g., ArangoDB)
│
├── llm_call/                    # Copy or install this module
│   ├── core/                    # Core validation logic
│   ├── validators/              # Built-in validators
│   ├── cli/                     # Optional CLI interface
│   └── litellm_integration.py   # Main integration point
│
└── your_code.py                 # Your project code
```

## Integration Methods

### Method 1: Direct Module Copy

```bash
# Copy the module to your project
cp -r /home/graham/workspace/experiments/marker/marker/llm_call \
      /home/graham/workspace/experiments/arangodb/

# Use in your code
from llm_call import completion_with_validation
```

### Method 2: Package Installation

```bash
# Build and install as package
cd /home/graham/workspace/experiments/marker/marker/llm_call
python -m build
pip install dist/llm_validation_loop-0.1.0-py3-none-any.whl

# Use anywhere
from llm_validation import completion_with_validation
```

## Usage Examples

### Basic Validation

```python
from llm_call import completion_with_validation
from pydantic import BaseModel

class QueryResponse(BaseModel):
    query: str
    explanation: str

result = completion_with_validation(
    messages=[{"role": "user", "content": "Generate an AQL query"}],
    response_format=QueryResponse,
    validators=["field_presence", "length_check"],
    max_retries=3
)
```

### Custom Validators

```python
from llm_call.decorators import validator
from llm_call.base import ValidationResult

@validator("aql_syntax")
class AQLValidator:
    def validate(self, response, context):
        # Custom AQL validation logic
        if "FOR" in response.query:
            return ValidationResult(valid=True)
        return ValidationResult(
            valid=False,
            error="AQL queries must contain FOR clause"
        )
```

### CLI Usage

```bash
# Validate a file
llm-validate validate query.json --validator aql_syntax

# Validate text directly
llm-validate validate-text "FOR u IN users RETURN u" --validator aql_syntax

# List available validators
llm-validate list-validators
```

## Key Features

1. **Modular Design**: Self-contained with no external dependencies
2. **Extensible**: Easy to add custom validators
3. **Protocol-based**: Uses Python protocols for flexibility
4. **CLI Support**: Optional command-line interface
5. **Async Ready**: Supports both sync and async operations

## ArangoDB-Specific Integration

```python
# Example: ArangoDB query validation
from llm_call import completion_with_validation
from llm_call.validators import create_validator

# Create custom ArangoDB validators
aql_validator = create_validator("aql_syntax")
doc_validator = create_validator("arango_doc")

# Generate and validate queries
def generate_optimized_query(description: str):
    return completion_with_validation(
        messages=[
            {"role": "system", "content": "You are an AQL expert"},
            {"role": "user", "content": f"Generate query: {description}"}
        ],
        response_format=AQLQuery,
        validators=[aql_validator],
        max_retries=3
    )
```

## Benefits

- ✅ No modification needed to existing code
- ✅ Drop-in integration
- ✅ Flexible validation strategies
- ✅ Production-ready error handling
- ✅ Comprehensive documentation
- ✅ Test coverage included