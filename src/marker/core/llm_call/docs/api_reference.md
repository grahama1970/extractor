# API Reference

Complete API reference for the LLM Validation Loop library.

## Core Functions

### completion_with_validation

Enhanced completion function with validation loop support.

```python
def completion_with_validation(
    model: str,
    messages: List[Dict[str, str]],
    response_format: Optional[type[BaseModel]] = None,
    validation_strategies: Optional[List[Union[str, ValidationStrategy]]] = None,
    max_retries: int = 3,
    enable_cache: bool = True,
    debug: bool = False,
) -> Any:
    """
    Enhanced completion function with validation loop support.
    
    Args:
        model: The model to use (e.g., "gemini/gemini-1.5-pro")
        messages: The messages to send to the model
        response_format: Optional Pydantic model for response validation
        validation_strategies: List of validation strategies to apply
        max_retries: Maximum number of retry attempts
        enable_cache: Whether to enable Redis caching
        debug: Enable debug mode for detailed logging
        
    Returns:
        The validated response from the model
    """
```

## Core Classes

### ValidationResult

Result of a validation operation.

```python
@dataclass
class ValidationResult:
    valid: bool
    error: Optional[str] = None
    debug_info: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None
```

### ValidationStrategy

Protocol for validation strategies.

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

### RetryConfig

Configuration for retry behavior.

```python
@dataclass
class RetryConfig:
    max_attempts: int = 3
    backoff_factor: float = 2.0
    initial_delay: float = 1.0
    max_delay: float = 60.0
    debug_mode: bool = False
    enable_cache: bool = True
```

## Decorators

### @validator

Decorator to register a validator.

```python
@validator("custom_validator")
class CustomValidator:
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        # Validation logic
        return ValidationResult(valid=True)
```

## Registry

### StrategyRegistry

Registry for validation strategies.

```python
class StrategyRegistry:
    def register(self, name: str, strategy_class: Type[ValidationStrategy]):
        """Register a validation strategy."""
    
    def get(self, name: str, **kwargs) -> ValidationStrategy:
        """Get a strategy instance."""
    
    def list_all(self) -> List[Dict[str, Any]]:
        """List all registered strategies."""
    
    def discover_strategies(self, path: Path):
        """Discover and load strategies from a directory."""
```

## Debug

### DebugManager

Manages debug information for validation runs.

```python
class DebugManager:
    def start_trace(self, strategy_name: str, context: Dict[str, Any]) -> ValidationTrace:
        """Start a new trace."""
    
    def end_trace(self, result: ValidationResult):
        """End the current trace."""
    
    def print_summary(self):
        """Print debug summary."""
```

### ValidationTrace

Trace information for a validation run.

```python
@dataclass
class ValidationTrace:
    strategy_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    result: Optional[ValidationResult] = None
    context: Dict[str, Any] = field(default_factory=dict)
    children: List['ValidationTrace'] = field(default_factory=list)
```

## Base Validators

### BaseValidator

Abstract base class for validators.

```python
class BaseValidator(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Validator name for debugging."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Validator description."""
        pass
    
    @abstractmethod
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate the response."""
        pass
```

## Service Classes

### ValidatedLiteLLMService

Enhanced LiteLLM service with validation loop support.

```python
class ValidatedLiteLLMService(LiteLLMService):
    enable_validation_loop: bool = False
    validation_strategies: List[str] = []
    validation_config: Dict[str, Any] = {}
    default_model: Optional[str] = None
    judge_model: Optional[str] = None
```

### EnhancedLiteLLMService

Enhanced LiteLLM service with optional validation.

```python
class EnhancedLiteLLMService(LiteLLMService):
    enable_validation_loop: bool = Field(default=False)
    validation_strategies: List[str] = Field(default_factory=list)
    json_schema_validation: bool = Field(default=True)
    max_validation_retries: int = Field(default=3)
```

## Retry Functions

### retry_with_validation

Async retry function with validation.

```python
async def retry_with_validation(
    llm_call: Callable,
    messages: List[Dict[str, str]],
    response_format: Optional[BaseModel],
    validation_strategies: List[ValidationStrategy],
    config: RetryConfig = None,
    **kwargs
) -> Any:
    """Retry LLM calls with validation."""
```

### retry_with_validation_sync

Synchronous version of retry_with_validation.

```python
def retry_with_validation_sync(
    llm_call: Callable,
    messages: List[Dict[str, str]],
    response_format: Optional[BaseModel],
    validation_strategies: List[ValidationStrategy],
    config: RetryConfig = None,
    **kwargs
) -> Any:
    """Synchronous retry with validation."""
```

## CLI Functions

### app

Main Typer application for CLI.

```python
app = typer.Typer(
    name="llm-validate",
    help="LLM validation with retry and custom strategies",
    add_completion=False,
)
```

## Utility Functions

### initialize_litellm_cache

Initialize Redis caching for LiteLLM.

```python
def initialize_litellm_cache():
    """Initialize Redis cache for LiteLLM responses."""
```

### load_config

Load configuration from JSON file.

```python
def load_config(path: Path) -> Dict[str, Any]:
    """Load configuration from JSON file."""
```

### save_validation_report

Save validation traces to a report file.

```python
def save_validation_report(traces: List[ValidationTrace], path: Path):
    """Save validation traces to a report file."""
```

## Exceptions

### ValidationError

Raised when validation fails after all retries.

```python
class ValidationError(Exception):
    """Raised when validation fails."""
```

### StrategyNotFoundError

Raised when a requested strategy is not found.

```python
class StrategyNotFoundError(ValueError):
    """Raised when a validation strategy is not found."""
```

## Environment Variables

Configuration via environment variables:

- `LITELLM_DEFAULT_MODEL`: Default model for LLM calls
- `LITELLM_JUDGE_MODEL`: Model for validation judgments
- `ENABLE_LLM_VALIDATION`: Enable/disable validation loop
- `REDIS_HOST`: Redis host for caching
- `REDIS_PORT`: Redis port for caching
- `REDIS_DB`: Redis database number
- `LITELLM_CACHE_TTL`: Cache time-to-live in seconds