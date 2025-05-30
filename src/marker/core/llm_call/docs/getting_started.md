# Getting Started

This guide will help you get up and running with the LLM Validation Loop quickly.

## Installation

### From PyPI

```bash
pip install llm-validation-loop
```

### From Source

```bash
git clone https://github.com/VikParuchuri/marker.git
cd marker/marker/llm_call
pip install -e .
```

### Development Installation

```bash
pip install -e ".[dev]"
```

## Basic Usage

### 1. Simple Validation

The simplest way to use the validation loop is with the `completion_with_validation` function:

```python
from llm_validation import completion_with_validation
from pydantic import BaseModel

class UserInfo(BaseModel):
    name: str
    age: int
    email: str

response = completion_with_validation(
    model="gemini/gemini-1.5-pro",
    messages=[
        {"role": "system", "content": "Extract user information."},
        {"role": "user", "content": "John Doe is 30 years old. Email: john@example.com"},
    ],
    response_format=UserInfo,
    validation_strategies=["field_presence(required_fields=['name', 'age', 'email'])"],
)

print(response)
# UserInfo(name='John Doe', age=30, email='john@example.com')
```

### 2. Using Multiple Validators

You can combine multiple validation strategies:

```python
response = completion_with_validation(
    model="gemini/gemini-1.5-pro",
    messages=messages,
    response_format=UserInfo,
    validation_strategies=[
        "field_presence(required_fields=['name', 'age', 'email'])",
        "range_check(field_name='age', min_value=0, max_value=150)",
        "format_check(field_name='email', pattern='^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$')",
    ],
    max_retries=3,
)
```

### 3. Enabling Debug Mode

Debug mode provides detailed information about the validation process:

```python
response = completion_with_validation(
    model="gemini/gemini-1.5-pro",
    messages=messages,
    response_format=UserInfo,
    validation_strategies=strategies,
    debug=True,  # Enable debug output
)
```

### 4. Using the CLI

List available validators:

```bash
llm-validate list-validators
```

Run validation from command line:

```bash
llm-validate validate "Extract user info from: John is 25" \
    --validators field_presence,age_range \
    --debug
```

## Configuration

### Environment Variables

Set these environment variables to configure default behavior:

```bash
export LITELLM_DEFAULT_MODEL="vertex_ai/gemini-2.5-flash-preview-04-17"
export LITELLM_JUDGE_MODEL="vertex_ai/gemini-2.5-flash-preview-04-17"
export ENABLE_LLM_VALIDATION="true"
```

### Redis Cache Configuration

The validation loop uses Redis for caching by default. Configure Redis connection:

```python
import os
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6379"
os.environ["REDIS_DB"] = "0"
```

## Next Steps

- Learn about [Core Concepts](core_concepts.md)
- Explore [Built-in Validators](validators.md)
- Create [Custom Validators](validators.md#custom-validators)
- Check out more [Examples](examples.md)