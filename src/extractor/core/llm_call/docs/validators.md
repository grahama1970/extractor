# Validators

Validators are the core of the validation system. This guide covers both built-in validators and how to create custom ones.

## Built-in Validators

### Base Validators

#### field_presence
Validates that required fields are present and non-empty.

```python
"field_presence(required_fields=['name', 'email', 'age'])"
```

#### length_check
Validates field length constraints.

```python
"length_check(field_name='description', min_length=10, max_length=500)"
```

#### format_check
Validates field format using regular expressions.

```python
"format_check(field_name='email', pattern='^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$')"
```

#### type_check
Validates field types.

```python
"type_check(field_name='age', expected_type='int')"
```

#### range_check
Validates numeric values are within a range.

```python
"range_check(field_name='score', min_value=0, max_value=100)"
```

### Table Validators

#### table_structure
Validates HTML table structure and dimensions.

```python
"table_structure(min_rows=2, max_rows=100, require_headers=True)"
```

#### table_consistency
Validates table consistency across rows.

```python
"table_consistency(check_column_count=True)"
```

### Image Validators

#### image_description
Validates image descriptions for completeness.

```python
"image_description(min_length=20, required_elements=['color', 'shape'])"
```

#### alt_text
Validates alt text for accessibility.

```python
"alt_text(min_length=10, max_length=125)"
```

### Math Validators

#### latex_syntax
Validates LaTeX mathematical expressions.

```python
"latex_syntax(check_delimiters=True, check_brackets=True)"
```

#### math_consistency
Validates mathematical consistency.

```python
"math_consistency(check_units=True, check_variables=True)"
```

### Code Validators

#### python_syntax
Validates Python code syntax.

```python
"python_syntax(check_imports=True, check_style=True)"
```

#### code_language
Validates code language detection.

```python
"code_language(expected_language='python')"
```

#### code_completeness
Validates code completeness.

```python
"code_completeness(require_main=True, require_docstrings=True)"
```

### Citation Validators

#### citation_match
Validates citations against reference texts using fuzzy matching.

```python
"citation_match(min_score=80.0)"
```

#### citation_format
Validates citation formatting.

```python
"citation_format(format_style='apa')"
```

### General Validators

#### content_quality
Validates general content quality metrics.

```python
"content_quality(min_words=100, forbidden_words=['spam'])"
```

#### tone_consistency
Validates tone and style consistency.

```python
"tone_consistency(expected_tone='professional')"
```

#### json_structure
Validates JSON structure and schema compliance.

```python
"json_structure(required_keys=['id', 'name', 'data'])"
```

## Custom Validators

### Creating a Basic Validator

```python
from llm_validation import validator, BaseValidator, ValidationResult

@validator("word_count")
class WordCountValidator(BaseValidator):
    def __init__(self, min_words: int = 10, max_words: int = 1000):
        self.min_words = min_words
        self.max_words = max_words
    
    @property
    def name(self) -> str:
        return f"word_count(min={self.min_words}, max={self.max_words})"
    
    @property
    def description(self) -> str:
        return "Validates word count is within range"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        text = str(response) if not isinstance(response, str) else response
        word_count = len(text.split())
        
        if self.min_words <= word_count <= self.max_words:
            return ValidationResult(
                valid=True,
                debug_info={"word_count": word_count}
            )
        else:
            return ValidationResult(
                valid=False,
                error=f"Word count {word_count} not in range {self.min_words}-{self.max_words}",
                suggestions=[f"Adjust text to be between {self.min_words} and {self.max_words} words"]
            )
```

### Using Custom Validators

```python
# Register happens automatically with @validator decorator
response = completion_with_validation(
    model="gemini/gemini-1.5-pro",
    messages=messages,
    response_format=MyModel,
    validation_strategies=["word_count(min=50, max=200)"]
)
```

### Advanced Validator Example

```python
from rapidfuzz import fuzz

@validator("similarity_check")
class SimilarityValidator(BaseValidator):
    """Validates that response is similar to expected output."""
    
    def __init__(self, expected_text: str, min_similarity: float = 0.8):
        self.expected_text = expected_text
        self.min_similarity = min_similarity * 100  # RapidFuzz uses 0-100 scale
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        response_text = str(response)
        similarity = fuzz.ratio(response_text, self.expected_text)
        
        if similarity >= self.min_similarity:
            return ValidationResult(
                valid=True,
                debug_info={
                    "similarity": similarity,
                    "threshold": self.min_similarity
                }
            )
        else:
            return ValidationResult(
                valid=False,
                error=f"Response similarity {similarity}% below threshold {self.min_similarity}%",
                suggestions=["Response should be more similar to expected output"],
                debug_info={
                    "similarity": similarity,
                    "expected_snippet": self.expected_text[:100] + "...",
                    "response_snippet": response_text[:100] + "..."
                }
            )
```

### Async Validators

```python
from llm_validation import AsyncValidator

@validator("async_api_check")
class AsyncAPIValidator(AsyncValidator):
    """Validates response against external API."""
    
    async def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        # Make async API call
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.example.com/validate/{response.id}") as resp:
                is_valid = await resp.json()
        
        return ValidationResult(
            valid=is_valid['status'] == 'ok',
            error=is_valid.get('error'),
            debug_info=is_valid
        )
```

### Validator Best Practices

1. **Clear Error Messages**: Provide specific, actionable error messages
2. **Helpful Suggestions**: Include suggestions for fixing validation errors
3. **Debug Information**: Add useful debug info for troubleshooting
4. **Parameter Validation**: Validate validator parameters in `__init__`
5. **Graceful Failures**: Handle edge cases and malformed responses
6. **Documentation**: Document what your validator does and how to use it

### Loading External Validators

```python
# From CLI
llm-validate add-validator ./my_validators/custom_validator.py

# From code
from llm_validation import registry
registry.load_from_file("./my_validators/custom_validator.py")
```

## Validator Composition

Validators can be composed for complex validation scenarios:

```python
# Sequential validation
strategies = [
    "field_presence(required_fields=['data'])",
    "json_structure(required_keys=['id', 'values'])",
    "custom_data_validation",
]

# Conditional validation based on context
def get_strategies(context):
    strategies = ["field_presence(required_fields=['content'])"]
    
    if context.get('strict_mode'):
        strategies.extend([
            "content_quality(min_words=100)",
            "tone_consistency(expected_tone='formal')",
        ])
    
    return strategies
```

## Performance Considerations

- Validators run sequentially by default
- Failed validators stop the chain early
- Use caching for expensive operations
- Consider async validators for I/O operations
- Profile validators in debug mode