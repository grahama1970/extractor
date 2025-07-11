# Core Concepts

Understanding the core concepts of the LLM Validation Loop will help you make the most of its features.

## Validation Results

Every validation returns a `ValidationResult` object:

```python
@dataclass
class ValidationResult:
    valid: bool
    error: Optional[str] = None
    debug_info: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None
```

- `valid`: Whether the validation passed
- `error`: Error message if validation failed
- `debug_info`: Additional debugging information
- `suggestions`: Suggestions for fixing validation errors

## Validation Strategies

A validation strategy is any class that implements the validation protocol:

```python
class ValidationStrategy(Protocol):
    @property
    def name(self) -> str:
        """Strategy name for debugging."""
        ...
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate the response."""
        ...
```

### Built-in Strategies

The library includes many pre-built strategies:

- **Base**: `field_presence`, `length_check`, `format_check`, etc.
- **Table**: `table_structure`, `table_consistency`
- **Image**: `image_description`, `alt_text`
- **Code**: `python_syntax`, `code_language`
- **Citation**: `citation_match`, `citation_format`
- **General**: `content_quality`, `tone_consistency`

## Retry Mechanism

The retry mechanism works by:

1. Making an initial LLM call
2. Running validation strategies
3. If validation fails, adding error feedback to the conversation
4. Retrying with the enhanced context
5. Repeating until validation passes or max retries reached

```python
config = RetryConfig(
    max_attempts=3,
    backoff_factor=2.0,
    initial_delay=1.0,
    max_delay=60.0,
    debug_mode=True
)
```

## Plugin Architecture

The validator registry allows dynamic loading of strategies:

```python
from llm_validation import validator, registry

@validator("custom_validator")
class CustomValidator:
    def validate(self, response, context):
        # Your validation logic
        return ValidationResult(valid=True)

# Use the validator
strategies = ["custom_validator"]
```

## Debug Infrastructure

The debug system provides comprehensive tracing:

```python
from llm_validation.core.debug import DebugManager

debug_manager = DebugManager()
trace = debug_manager.start_trace("validation_run", context)
# ... validation logic ...
debug_manager.end_trace(result)
debug_manager.print_summary()
```

## Caching

Redis caching is built-in for improved performance:

```python
from marker.services.utils.litellm_cache import initialize_litellm_cache

# Initialize cache (done automatically)
initialize_litellm_cache()

# Cache configuration
os.environ["LITELLM_CACHE_TTL"] = "3600"  # 1 hour
os.environ["LITELLM_CACHE_ENABLED"] = "true"
```

## Context Passing

Context is passed through the validation pipeline:

```python
context = {
    "attempt": 0,
    "references": ["source text"],
    "metadata": {"user_id": "123"}
}

result = validator.validate(response, context)
```

This allows validators to access:
- Current retry attempt
- Reference materials
- Custom metadata
- Previous validation results

## Error Handling

The system handles errors gracefully:

```python
try:
    response = completion_with_validation(...)
except ValidationError as e:
    print(f"Validation failed: {e}")
except LiteLLMError as e:
    print(f"LLM error: {e}")
```

## Composable Validators

Validators can be composed for complex validation:

```python
strategies = [
    "field_presence(required_fields=['name'])",
    "length_check(field_name='name', min_length=2)",
    "format_check(field_name='email', pattern='email')",
    "custom_business_logic",
]
```

The system runs all validators and aggregates results.