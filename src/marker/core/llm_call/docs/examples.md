# Examples

This guide provides practical examples of using the marker-llm-call validation system.

## Basic Examples

### Table Validation

```python
from marker.llm_call import create_validator

# Create a table validator
validator = create_validator("table", min_rows=2, min_cols=3)

# Validate table data
table_data = {
    "headers": ["Name", "Age", "City"],
    "rows": [
        ["John", 30, "NYC"],
        ["Jane", 25, "LA"]
    ]
}

result = validator.validate(table_data)
if result.valid:
    print("Table is valid!")
else:
    print(f"Validation error: {result.error}")
```

### Image Description Validation

```python
from marker.llm_call import create_validator

# Create an image validator
validator = create_validator("image", min_description_length=20)

# Validate image metadata
image_data = {
    "alt_text": "A beautiful sunset over the ocean with orange and pink hues",
    "width": 1920,
    "height": 1080,
    "format": "jpg"
}

result = validator.validate(image_data)
print(f"Valid: {result.valid}")
```

## Integration with LiteLLM

### Basic LLM Call with Validation

```python
from marker.llm_call import completion_with_validation
from marker.llm_call.validators import TableValidator
from pydantic import BaseModel
from typing import List

class TableOutput(BaseModel):
    headers: List[str]
    rows: List[List[str]]

# Create validators
validators = [
    TableValidator(min_rows=3, min_cols=2)
]

# Make LLM call with validation
result = completion_with_validation(
    messages=[
        {"role": "user", "content": "Create a table of US presidents with name and term"}
    ],
    response_format=TableOutput,
    validators=validators,
    max_retries=3
)

print(result.headers)  # ["Name", "Term"]
print(result.rows[0])  # ["George Washington", "1789-1797"]
```

### Math Expression Validation

```python
from marker.llm_call import completion_with_validation
from marker.llm_call.validators import MathValidator
from pydantic import BaseModel

class MathSolution(BaseModel):
    equation: str
    solution: float
    steps: List[str]

# Create math validator
validators = [
    MathValidator(format="latex", check_balanced=True)
]

# Solve math problem with validation
result = completion_with_validation(
    messages=[
        {"role": "user", "content": "Solve x^2 + 5x + 6 = 0"}
    ],
    response_format=MathSolution,
    validators=validators
)

print(f"Equation: {result.equation}")
print(f"Solution: {result.solution}")
```

## Advanced Examples

### Multi-Validator Pipeline

```python
from marker.llm_call import create_validator
from marker.llm_call.base import ValidationResult

# Create multiple validators
validators = [
    create_validator("general", min_length=10, max_length=1000),
    create_validator("code", language="python", check_syntax=True),
    create_validator("citation", min_score=85)
]

def validate_complex_content(content):
    """Validate content with multiple validators"""
    results = []
    
    for validator in validators:
        result = validator.validate(content)
        results.append(result)
        
        if not result.valid:
            print(f"{validator.__class__.__name__} failed: {result.error}")
            return False
    
    return True

# Usage
content = {
    "text": "Here's a Python function to calculate fibonacci numbers...",
    "code": "def fib(n): return n if n <= 1 else fib(n-1) + fib(n-2)",
    "citation": "As noted by Knuth (1997), recursive solutions..."
}

is_valid = validate_complex_content(content)
```

### Custom Validator

```python
from marker.llm_call.base import ValidationStrategy, ValidationResult
from marker.llm_call import register_validator

@register_validator("custom")
class CustomValidator(ValidationStrategy):
    """Custom validator for specific business logic"""
    
    def __init__(self, required_keywords=None):
        self.required_keywords = required_keywords or []
    
    def validate(self, content: Any) -> ValidationResult:
        # Convert content to string for keyword checking
        text = str(content).lower()
        
        # Check for required keywords
        missing_keywords = []
        for keyword in self.required_keywords:
            if keyword.lower() not in text:
                missing_keywords.append(keyword)
        
        if missing_keywords:
            return ValidationResult(
                valid=False,
                error=f"Missing required keywords: {', '.join(missing_keywords)}",
                suggestions=[f"Add keyword: {kw}" for kw in missing_keywords]
            )
        
        return ValidationResult(valid=True)

# Usage
validator = create_validator("custom", required_keywords=["important", "critical"])
result = validator.validate("This is an important and critical document")
print(result.valid)  # True
```

### Async Validation

```python
import asyncio
from marker.llm_call import acompletion_with_validation
from marker.llm_call.validators import TableValidator

async def validate_tables_async():
    """Validate multiple tables asynchronously"""
    
    validators = [TableValidator(min_rows=2)]
    
    # Create multiple validation tasks
    tasks = []
    for i in range(3):
        task = acompletion_with_validation(
            messages=[
                {"role": "user", "content": f"Create table {i} with data"}
            ],
            response_format=TableOutput,
            validators=validators
        )
        tasks.append(task)
    
    # Wait for all validations to complete
    results = await asyncio.gather(*tasks)
    
    for i, result in enumerate(results):
        print(f"Table {i}: {len(result.rows)} rows")

# Run async validation
asyncio.run(validate_tables_async())
```

## CLI Examples

### Basic CLI Usage

```bash
# Validate a table file
marker-llm-call validate tables/sales.json --validator table

# Validate with parameters
marker-llm-call validate data.json --validator table --params min_rows=5 --params min_cols=3

# Validate text directly
marker-llm-call validate-text "E = mc^2" --validator math --params format=ascii
```

### Batch Processing

```bash
#!/bin/bash
# validate_all.sh - Validate all JSON files in a directory

for file in data/*.json; do
    echo "Validating $file..."
    marker-llm-call validate "$file" --validator general
    
    if [ $? -eq 0 ]; then
        echo "✓ $file passed validation"
    else
        echo "✗ $file failed validation"
    fi
done
```

### Integration with jq

```bash
# Extract and validate specific fields
cat document.json | jq '.tables[]' | \
    marker-llm-call validate-text - --validator table --output-format json | \
    jq '.valid'
```

## Error Handling

```python
from marker.llm_call import completion_with_validation
from marker.llm_call.exceptions import ValidationError, RetryExhaustedError

try:
    result = completion_with_validation(
        messages=[{"role": "user", "content": "Generate a table"}],
        response_format=TableOutput,
        validators=[TableValidator(min_rows=10)],
        max_retries=3
    )
except ValidationError as e:
    print(f"Validation failed: {e}")
except RetryExhaustedError as e:
    print(f"All retries exhausted: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Testing

```python
import pytest
from marker.llm_call import create_validator

def test_table_validator():
    """Test table validation"""
    validator = create_validator("table", min_rows=2, min_cols=2)
    
    # Valid table
    valid_table = {
        "headers": ["A", "B"],
        "rows": [["1", "2"], ["3", "4"]]
    }
    result = validator.validate(valid_table)
    assert result.valid
    
    # Invalid table (too few rows)
    invalid_table = {
        "headers": ["A", "B"],
        "rows": [["1", "2"]]
    }
    result = validator.validate(invalid_table)
    assert not result.valid
    assert "rows" in result.error.lower()

def test_citation_validator():
    """Test citation validation"""
    validator = create_validator("citation", min_score=80)
    
    # Valid citation
    citation = "Smith et al. (2023) demonstrated that..."
    result = validator.validate(citation)
    assert result.valid
```

## Real-World Use Cases

### Document Processing Pipeline

```python
from marker.llm_call import completion_with_validation
from marker.llm_call.validators import TableValidator, CitationValidator
import json

class DocumentProcessor:
    """Process documents with validation"""
    
    def __init__(self):
        self.table_validator = TableValidator(min_rows=1)
        self.citation_validator = CitationValidator(min_score=75)
    
    def extract_tables(self, document_text):
        """Extract and validate tables from document"""
        
        # Extract tables using LLM
        result = completion_with_validation(
            messages=[
                {"role": "system", "content": "Extract all tables from the document"},
                {"role": "user", "content": document_text}
            ],
            response_format=TablesOutput,
            validators=[self.table_validator],
            max_retries=2
        )
        
        return result.tables
    
    def validate_citations(self, text, references):
        """Validate all citations in text"""
        
        # Extract citations
        citations = self.extract_citations(text)
        
        # Validate each citation
        valid_citations = []
        for citation in citations:
            result = self.citation_validator.validate({
                "citation": citation,
                "references": references
            })
            
            if result.valid:
                valid_citations.append(citation)
            else:
                print(f"Invalid citation: {citation} - {result.error}")
        
        return valid_citations

# Usage
processor = DocumentProcessor()
tables = processor.extract_tables(document_content)
print(f"Extracted {len(tables)} valid tables")
```

### Quality Assurance System

```python
from marker.llm_call import create_validator
import logging

class QASystem:
    """Quality assurance system with validation"""
    
    def __init__(self):
        self.validators = {
            "code": create_validator("code", language="python"),
            "math": create_validator("math", format="latex"),
            "general": create_validator("general", min_length=10)
        }
        self.logger = logging.getLogger(__name__)
    
    def validate_content(self, content_type, content):
        """Validate content based on type"""
        
        validator = self.validators.get(content_type)
        if not validator:
            self.logger.warning(f"No validator for type: {content_type}")
            return True
        
        result = validator.validate(content)
        
        if not result.valid:
            self.logger.error(f"Validation failed: {result.error}")
            if result.suggestions:
                self.logger.info(f"Suggestions: {result.suggestions}")
        
        return result.valid
    
    def batch_validate(self, items):
        """Validate multiple items"""
        
        results = []
        for item in items:
            is_valid = self.validate_content(
                item["type"], 
                item["content"]
            )
            results.append({
                "id": item["id"],
                "valid": is_valid
            })
        
        return results

# Usage
qa = QASystem()
items = [
    {"id": 1, "type": "code", "content": "def hello(): pass"},
    {"id": 2, "type": "math", "content": "\\frac{1}{2}"},
    {"id": 3, "type": "general", "content": "This is a test"}
]

results = qa.batch_validate(items)
print(f"Valid items: {sum(1 for r in results if r['valid'])}/{len(results)}")
```

## Performance Optimization

```python
from marker.llm_call import completion_with_validation
from marker.llm_call.cache import get_cache
import time

# Enable caching for repeated validations
cache = get_cache()

def cached_validation(content, validator_type="general"):
    """Validate with caching"""
    
    # Create cache key
    cache_key = f"validation:{validator_type}:{hash(str(content))}"
    
    # Check cache
    cached_result = cache.get(cache_key)
    if cached_result:
        return cached_result
    
    # Perform validation
    validator = create_validator(validator_type)
    result = validator.validate(content)
    
    # Cache result
    cache.set(cache_key, result, expire=3600)  # 1 hour
    
    return result

# Benchmark
start = time.time()
for i in range(100):
    cached_validation("Test content", "general")
end = time.time()
print(f"Time with cache: {end - start:.2f}s")
```

## See Also

- [Getting Started Guide](getting_started.md)
- [API Reference](api_reference.md)
- [Architecture](architecture.md)
- [CLI Reference](cli_reference.md)