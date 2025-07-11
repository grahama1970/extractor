# Architecture

This document describes the architecture of the marker-llm-call validation system.

## Overview

The marker-llm-call system is designed as a modular, extensible validation framework that integrates with LiteLLM and the Marker project. The architecture follows a 3-layer design pattern:

1. **Core Layer**: Base validation interfaces and retry logic
2. **Validators Layer**: Specific validation implementations
3. **Integration Layer**: LiteLLM service integration

```
┌─────────────────────────────────────────────────────────────┐
│                        Applications                          │
│                   (Marker, CLI, Custom)                      │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   Integration Layer                          │
│              (LiteLLM Service Integration)                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                    Validators Layer                          │
│        (Table, Image, Math, Code, Citation, etc.)           │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      Core Layer                              │
│            (Base Classes, Protocols, Retry)                  │
└─────────────────────────────────────────────────────────────┘
```

## Component Architecture

### Core Layer (`marker.llm_call.core`)

The core layer provides fundamental abstractions and utilities:

```python
# base.py - Core interfaces
@dataclass
class ValidationResult:
    valid: bool
    error: Optional[str]
    debug_info: Optional[Dict[str, Any]]
    suggestions: Optional[List[str]]

class ValidationStrategy(Protocol):
    def validate(self, content: Any) -> ValidationResult:
        ...

# retry.py - Retry mechanism
@dataclass
class RetryConfig:
    max_retries: int = 3
    backoff_factor: float = 2.0
    max_delay: float = 60.0

def retry_with_validation(
    llm_call: Callable,
    messages: List[Dict[str, str]],
    response_format: Optional[BaseModel],
    validation_strategies: List[ValidationStrategy],
    config: RetryConfig = None,
    **kwargs
) -> Any:
    ...
```

### Validators Layer (`marker.llm_call.validators`)

Specific validators implementing the `ValidationStrategy` protocol:

```python
# table.py
class TableValidator(ValidationStrategy):
    def __init__(self, min_rows=1, min_cols=2):
        self.min_rows = min_rows
        self.min_cols = min_cols
    
    def validate(self, content: Any) -> ValidationResult:
        # Table-specific validation logic
        ...

# citation.py - Uses RapidFuzz for matching
class CitationValidator(ValidationStrategy):
    def __init__(self, min_score=80):
        self.min_score = min_score
    
    def validate(self, content: Any) -> ValidationResult:
        # Citation validation with fuzzy matching
        ...
```

### Integration Layer (`marker.llm_call.litellm_integration`)

Integrates with Marker's existing LiteLLMService:

```python
def completion_with_validation(
    messages: List[Dict[str, str]],
    response_format: Optional[BaseModel] = None,
    validators: Optional[List[ValidationStrategy]] = None,
    max_retries: int = 3,
    **kwargs
) -> Any:
    """Main integration function following user's pattern"""
    
    # Initialize caching and settings
    initialize_litellm_cache()
    litellm.enable_json_schema_validation = True
    
    # Get service instance
    service = get_llm_service()
    
    # Use retry mechanism with validation
    return retry_with_validation(
        llm_call=service.call,
        messages=messages,
        response_format=response_format,
        validation_strategies=validators or [],
        config=RetryConfig(max_retries=max_retries),
        **kwargs
    )
```

## Design Patterns

### 1. Protocol Pattern

The system uses Python's Protocol pattern for extensibility:

```python
class ValidationStrategy(Protocol):
    """Protocol for validation strategies"""
    def validate(self, content: Any) -> ValidationResult:
        ...
```

This allows for:
- Type safety without inheritance
- Easy extension with new validators
- Clear interface contracts

### 2. Factory Pattern

Validator creation uses a factory pattern:

```python
@validator("table")
class TableValidator:
    ...

def create_validator(validator_type: str, **kwargs) -> ValidationStrategy:
    """Factory function for creating validators"""
    validator_class = VALIDATOR_REGISTRY.get(validator_type)
    if not validator_class:
        raise ValueError(f"Unknown validator: {validator_type}")
    return validator_class(**kwargs)
```

### 3. Registry Pattern

Validators are registered using a decorator pattern:

```python
def validator(name: str):
    """Decorator to register validators"""
    def decorator(cls):
        VALIDATOR_REGISTRY[name] = cls
        return cls
    return decorator
```

### 4. Chain of Responsibility

Multiple validators can be chained:

```python
def validate_with_chain(content, validators):
    """Chain multiple validators"""
    for validator in validators:
        result = validator.validate(content)
        if not result.valid:
            return result
    return ValidationResult(valid=True)
```

## Data Flow

1. **Input Processing**:
   ```
   User Input → Message Formatting → LLM Service
   ```

2. **LLM Processing**:
   ```
   LLM Service → Raw Response → JSON Parsing → Pydantic Model
   ```

3. **Validation Loop**:
   ```
   Pydantic Model → Validators → ValidationResult
                          ↓
                    [If Invalid]
                          ↓
                  Retry with Context → LLM Service
   ```

4. **Output**:
   ```
   Valid Result → Application
   ```

## Integration Points

### 1. LiteLLMService Integration

The system integrates with Marker's existing LiteLLMService:

```python
def get_llm_service():
    """Get or create LiteLLMService instance"""
    if not hasattr(get_llm_service, "_instance"):
        get_llm_service._instance = LiteLLMService(
            model=os.environ.get("LITELLM_DEFAULT_MODEL")
        )
    return get_llm_service._instance
```

### 2. Redis Caching

Uses Marker's Redis caching infrastructure:

```python
def initialize_litellm_cache():
    """Initialize Redis caching"""
    cache_type = os.environ.get("MARKER_LLM_CACHE_TYPE", "redis")
    if cache_type == "redis":
        import litellm
        litellm.cache = Cache(
            type="redis",
            host=os.environ.get("MARKER_LLM_REDIS_HOST", "localhost"),
            port=int(os.environ.get("MARKER_LLM_REDIS_PORT", "6379"))
        )
```

### 3. Environment Configuration

Follows Marker's environment variable patterns:

```python
# Default model configuration
DEFAULT_MODEL = os.environ.get(
    "LITELLM_DEFAULT_MODEL",
    "vertex_ai/gemini-1.5-flash"
)

# Judge model for validation
JUDGE_MODEL = os.environ.get(
    "LITELLM_JUDGE_MODEL",
    "vertex_ai/gemini-1.5-flash"
)
```

## Extensibility

### Adding New Validators

1. Create a new validator class:
   ```python
   @validator("custom")
   class CustomValidator(ValidationStrategy):
       def validate(self, content: Any) -> ValidationResult:
           # Custom validation logic
           ...
   ```

2. Register automatically via decorator:
   ```python
   # The @validator decorator handles registration
   ```

3. Use in application:
   ```python
   validator = create_validator("custom", param1=value1)
   ```

### Custom Retry Logic

Override default retry behavior:

```python
custom_config = RetryConfig(
    max_retries=5,
    backoff_factor=1.5,
    max_delay=30.0
)

result = completion_with_validation(
    messages=messages,
    validators=validators,
    config=custom_config
)
```

### Integration with Other Services

The architecture supports integration with other services:

```python
class ExternalValidator(ValidationStrategy):
    def __init__(self, api_endpoint):
        self.api_endpoint = api_endpoint
    
    def validate(self, content: Any) -> ValidationResult:
        # Call external API for validation
        response = requests.post(self.api_endpoint, json=content)
        return ValidationResult(
            valid=response.json()["valid"],
            error=response.json().get("error")
        )
```

## Performance Considerations

### 1. Caching

- Redis caching for repeated validations
- In-memory fallback for development
- Configurable TTL for cache entries

### 2. Async Support

Full async support for concurrent validations:

```python
async def acompletion_with_validation(
    messages: List[Dict[str, str]],
    response_format: Optional[BaseModel] = None,
    validators: Optional[List[ValidationStrategy]] = None,
    **kwargs
) -> Any:
    # Async implementation
    ...
```

### 3. Batching

Support for batch validation:

```python
def batch_validate(items, validator):
    """Validate multiple items efficiently"""
    return [validator.validate(item) for item in items]
```

## Security Considerations

### 1. Input Validation

- All inputs are validated before processing
- Pydantic models ensure type safety
- Size limits prevent DoS attacks

### 2. Environment Variables

- Sensitive configuration via environment variables
- No hardcoded credentials
- Follows Marker's security patterns

### 3. Error Handling

- Graceful error handling
- No sensitive information in error messages
- Proper logging for debugging

## Testing Architecture

### 1. Unit Tests

```python
def test_table_validator():
    validator = TableValidator(min_rows=2)
    result = validator.validate(valid_table)
    assert result.valid
```

### 2. Integration Tests

```python
@pytest.mark.integration
def test_litellm_integration():
    result = completion_with_validation(
        messages=messages,
        validators=[TableValidator()]
    )
    assert result is not None
```

### 3. Mocking

```python
@patch('litellm.completion')
def test_with_mock(mock_completion):
    mock_completion.return_value = mock_response
    # Test logic
```

## Deployment

### 1. Package Structure

```
marker-llm-call/
├── marker/
│   └── llm_call/
│       ├── __init__.py
│       ├── core/
│       ├── validators/
│       └── litellm_integration.py
├── setup.py
└── pyproject.toml
```

### 2. Dependencies

- Required: `litellm`, `pydantic`, `rapidfuzz`
- Optional: `redis`, `rich`, `typer`
- Development: `pytest`, `black`, `mypy`

### 3. Configuration

Environment-based configuration:

```bash
export LITELLM_DEFAULT_MODEL="vertex_ai/gemini-1.5-flash"
export MARKER_LLM_CACHE_TYPE="redis"
export MARKER_LLM_REDIS_HOST="localhost"
export MARKER_LLM_REDIS_PORT="6379"
```

## Future Enhancements

### 1. Plugin System

- Dynamic validator loading
- Plugin discovery mechanism
- Third-party validator support

### 2. Metrics and Monitoring

- Validation success rates
- Performance metrics
- Error tracking

### 3. Advanced Features

- ML-based validation
- Custom scoring algorithms
- Multi-language support

## See Also

- [Getting Started Guide](getting_started.md)
- [API Reference](api_reference.md)
- [Examples](examples.md)
- [Contributing](contributing.md)