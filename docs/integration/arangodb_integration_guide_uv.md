# ArangoDB-Marker Integration Guide (with uv)

This guide provides instructions for integrating ArangoDB with the Marker project using the LLM validation system, with specific support for uv package management.

## Step 1: Copy the Module

```bash
# From the marker directory
cd /home/graham/workspace/experiments/marker
cp -r marker/llm_call /home/graham/workspace/experiments/arangodb/
```

## Step 2: Install Dependencies with uv

```bash
cd /home/graham/workspace/experiments/arangodb
source .venv/bin/activate  # Make sure you're in the virtual environment

# Install dependencies with uv
uv pip install litellm pydantic loguru rapidfuzz redis typer rich beautifulsoup4
```

## Step 3: Create Custom ArangoDB Validators

Create a custom validator for ArangoDB Query Language (AQL) to ensure generated queries follow the correct syntax:

File: `/home/graham/workspace/experiments/arangodb/llm_call/validators/arangodb.py`

```python
"""
ArangoDB-specific validators for LLM responses.
These validators ensure AQL queries and other ArangoDB-related content 
meets required standards.
"""

from llm_call.validators.base import ValidationStrategy
from llm_call.cli.schemas import ValidationResult
from llm_call.decorators import validator
from typing import Any, Dict, List, Optional, Union


@validator("aql")
class AQLValidator(ValidationStrategy):
    """Validates ArangoDB Query Language syntax."""
    
    def __init__(self, check_syntax=True, max_complexity=10):
        """Initialize AQL validator.
        
        Args:
            check_syntax: Whether to check basic AQL syntax
            max_complexity: Maximum allowed query complexity (measured by FOR/LET statements)
        """
        self.check_syntax = check_syntax
        self.max_complexity = max_complexity
    
    def validate(self, content: Union[str, Dict], context: Optional[Dict] = None) -> ValidationResult:
        """Validate AQL query syntax.
        
        Args:
            content: The query string or object with a 'query' attribute
            context: Optional context for validation
            
        Returns:
            ValidationResult: Validation result with suggestions if invalid
        """
        # Extract query string from various input types
        if isinstance(content, str):
            query = content
        elif hasattr(content, 'query'):
            query = content.query
        elif isinstance(content, dict) and 'query' in content:
            query = content['query']
        else:
            return ValidationResult(
                valid=False,
                error="Cannot extract query from content",
                suggestions=["Provide a string or object with 'query' attribute"]
            )
        
        # Check for required AQL keywords
        keywords = ["FOR", "RETURN", "FILTER", "INSERT", "UPDATE", "REMOVE"]
        if not any(kw in query.upper() for kw in keywords):
            return ValidationResult(
                valid=False,
                error="Query must contain AQL operations",
                suggestions=[
                    "Add FOR/RETURN clause",
                    "Use FILTER for conditions",
                    "Include INSERT/UPDATE/REMOVE for modifications"
                ]
            )
        
        # Check query complexity
        if self.check_syntax:
            complexity = query.upper().count("FOR") + query.upper().count("LET")
            if complexity > self.max_complexity:
                return ValidationResult(
                    valid=False,
                    error=f"Query too complex ({complexity} FOR/LET statements)",
                    suggestions=[
                        "Simplify the query",
                        "Break into multiple smaller queries",
                        "Use views or indices to optimize"
                    ]
                )
        
        # Query passes all validation checks
        return ValidationResult(valid=True)
```

## Step 4: Build and Install as Package (Alternative)

If you prefer to install it as a package:

```bash
cd /home/graham/workspace/experiments/marker/marker/llm_call

# Build the package
python -m build

# Install with uv
cd /home/graham/workspace/experiments/arangodb
source .venv/bin/activate
uv pip install /home/graham/workspace/experiments/marker/marker/llm_call/dist/llm_validation_loop-0.1.0-py3-none-any.whl
```

## Step 5: Test CLI with Proper Setup

```bash
cd /home/graham/workspace/experiments/marker
source .venv/bin/activate
export PYTHONPATH=/home/graham/workspace/experiments/marker/

# Test the CLI
python -m marker.llm_call.cli.app --help
python -m marker.llm_call.cli.app list-validators
```

## Step 6: Create Test Script for ArangoDB

Create `/home/graham/workspace/experiments/arangodb/test_llm_validation.py`:

```python
#!/usr/bin/env python3
"""Test LLM validation in ArangoDB environment."""

import os
import sys
import json

# Add the llm_call module to path
sys.path.insert(0, '/home/graham/workspace/experiments/arangodb')

from llm_call import completion_with_validation
from llm_call.validators import create_validator
from llm_call.decorators import validator
from llm_call.cli.schemas import ValidationResult
from pydantic import BaseModel
from typing import Dict, Optional

# Create custom ArangoDB validator if it doesn't exist
try:
    validator = create_validator("aql")
    print("Using existing AQL validator")
except Exception:
    print("Creating custom AQL validator")
    
    @validator("aql")
    class AQLValidator:
        """Validates ArangoDB Query Language syntax."""
        
        def __init__(self, check_syntax=True):
            self.check_syntax = check_syntax
        
        def validate(self, response, context: Optional[Dict] = None) -> ValidationResult:
            query = response if isinstance(response, str) else response.query
            
            # Check for required AQL keywords
            keywords = ["FOR", "RETURN", "INSERT", "UPDATE", "REMOVE"]
            if not any(kw in query.upper() for kw in keywords):
                return ValidationResult(
                    valid=False,
                    error="Query must contain AQL operations",
                    suggestions=["Add FOR/RETURN clause"]
                )
            
            return ValidationResult(valid=True)

# Define test models
class AQLQuery(BaseModel):
    query: str
    explanation: str

# Test valid query
validator = create_validator("aql")
test_valid = AQLQuery(
    query="FOR u IN users FILTER u.age > 18 RETURN u",
    explanation="Find all adult users"
)

valid_result = validator.validate(test_valid)
print(f"Valid query test: {'✓ PASS' if valid_result.valid else '✗ FAIL'}")

# Test invalid query
test_invalid = AQLQuery(
    query="SELECT * FROM users WHERE age > 18",
    explanation="Find all adult users using SQL"
)

invalid_result = validator.validate(test_invalid)
print(f"Invalid query test: {'✓ PASS' if not invalid_result.valid else '✗ FAIL'}")
if not invalid_result.valid:
    print(f"  Error: {invalid_result.error}")
    print(f"  Suggestions: {invalid_result.suggestions}")

# Create debug output directory
os.makedirs("debug_output", exist_ok=True)

# Save test results
results = {
    "valid_test": {
        "query": test_valid.query,
        "result": {
            "valid": valid_result.valid,
            "error": valid_result.error,
            "suggestions": valid_result.suggestions
        }
    },
    "invalid_test": {
        "query": test_invalid.query,
        "result": {
            "valid": invalid_result.valid,
            "error": invalid_result.error,
            "suggestions": invalid_result.suggestions
        }
    }
}

# Write results to file
with open("debug_output/aql_validation_test.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\nResults saved to debug_output/aql_validation_test.json")
print(f"\n{'✓ All tests PASSED' if valid_result.valid and not invalid_result.valid else '✗ Some tests FAILED'}")
```

## Step 7: Integration with Corpus Validation

The corpus validator CLI can be used for city validation between modules:

1. First, ensure the allowed_cities.txt file exists:

```bash
cd /home/graham/workspace/experiments/marker
echo "New York
London
Tokyo
Paris
Berlin
Singapore
Sydney
Toronto
Dubai
San Francisco" > allowed_cities.txt
```

2. Use the corpus validator:

```bash
python corpus_validator_cli.py "London" --corpus-file allowed_cities.txt
```

## Step 8: Environment Setup

Make sure your ArangoDB `.env` includes:

```bash
PYTHONPATH=/home/graham/workspace/experiments/arangodb/
LITELLM_DEFAULT_MODEL=vertex_ai/gemini-2.5-flash-preview-04-17
REDIS_HOST=localhost
```

## Step 9: Use in ArangoDB Project

In your ArangoDB code:

```python
from llm_call import completion_with_validation
from llm_call.validators import create_validator
from pydantic import BaseModel
from typing import Dict, List, Optional

# Define response model
class AQLQuery(BaseModel):
    query: str
    explanation: str
    bind_vars: Dict = {}

# Use validation
validators = [
    create_validator("aql"),
    create_validator("content_quality", min_words=5)
]

# Generate validated AQL query
result = completion_with_validation(
    messages=[
        {"role": "system", "content": "You are an AQL expert."},
        {"role": "user", "content": "Generate AQL query to find active users"}
    ],
    response_format=AQLQuery,
    validators=validators,
    max_retries=3
)

print(f"Query: {result.query}")
print(f"Explanation: {result.explanation}")
```

## Step 10: Verification

Run the verification script to check if everything is properly integrated:

```bash
cd /home/graham/workspace/experiments/marker
python corpus_validator_cli.py --check

# Or for comprehensive verification
python test_arangodb_integration_verification.py
```

## Correct uv Commands Summary

```bash
# Install dependencies
uv pip install litellm pydantic loguru rapidfuzz redis typer

# Install from local package
uv pip install /path/to/package.whl

# Install in development mode
uv pip install -e /path/to/package/

# List installed packages
uv pip list

# Show package info
uv pip show litellm
```

The integration is now complete with proper uv package management support!