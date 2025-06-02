# ArangoDB Integration Guide for LLM Validation

## Step 1: Copy the Module

```bash
# From the marker directory
cd /home/graham/workspace/experiments/marker
cp -r marker/llm_call /home/graham/workspace/experiments/arangodb/
```

## Step 2: Install Dependencies

```bash
cd /home/graham/workspace/experiments/arangodb
pip install litellm pydantic loguru rapidfuzz redis typer rich beautifulsoup4
```

## Step 3: Create ArangoDB-Specific Validators

Create `/home/graham/workspace/experiments/arangodb/llm_call/validators/arangodb.py`:

```python
from llm_call.decorators import validator
from llm_call.base import ValidationResult

@validator("aql")
class AQLValidator:
    """Validates ArangoDB Query Language syntax."""
    
    def __init__(self, check_syntax=True, max_complexity=10):
        self.check_syntax = check_syntax
        self.max_complexity = max_complexity
    
    def validate(self, response, context):
        query = response if isinstance(response, str) else response.query
        
        # Check for required AQL keywords
        keywords = ["FOR", "RETURN", "INSERT", "UPDATE", "REMOVE"]
        if not any(kw in query.upper() for kw in keywords):
            return ValidationResult(
                valid=False,
                error="Query must contain AQL operations",
                suggestions=["Add FOR/RETURN clause"]
            )
        
        # Check complexity
        complexity = query.count("FOR") + query.count("LET")
        if complexity > self.max_complexity:
            return ValidationResult(
                valid=False,
                error=f"Query too complex ({complexity})",
                suggestions=["Simplify the query"]
            )
        
        return ValidationResult(valid=True)
```

## Step 4: Use in ArangoDB Code

```python
from llm_call import completion_with_validation
from pydantic import BaseModel

class AQLQuery(BaseModel):
    query: str
    bind_vars: dict = {}

# Generate validated AQL
result = completion_with_validation(
    messages=[
        {"role": "system", "content": "You are an AQL expert"},
        {"role": "user", "content": "Find all users over 18"}
    ],
    response_format=AQLQuery,
    validators=["aql"],
    max_retries=3
)

# Use the validated query
print(result.query)  # FOR u IN users FILTER u.age > 18 RETURN u
```

## Step 5: CLI Usage in ArangoDB

```bash
# Navigate to ArangoDB project
cd /home/graham/workspace/experiments/arangodb

# List available validators
python -m llm_call.cli.app list-validators

# Validate an AQL query file
python -m llm_call.cli.app validate query.aql --validators aql

# Test a query directly
echo "FOR u IN users RETURN u" > test.aql
python -m llm_call.cli.app validate test.aql --validators aql
```

## Step 6: Integration Example

Create `/home/graham/workspace/experiments/arangodb/test_integration.py`:

```python
#!/usr/bin/env python3
"""Test LLM validation integration with ArangoDB."""

from llm_call import completion_with_validation
from llm_call.validators import create_validator
from pydantic import BaseModel
import json

# Define models
class AQLQuery(BaseModel):
    query: str
    explanation: str
    
class DocumentSchema(BaseModel):
    collection: str
    fields: list[str]

# Create validators
aql_validator = create_validator("aql", check_syntax=True)
table_validator = create_validator("table_structure", min_rows=1)

# Test 1: Generate AQL query
print("Generating AQL query...")
query_result = completion_with_validation(
    messages=[
        {"role": "user", "content": "Create AQL to find all active users"}
    ],
    response_format=AQLQuery,
    validators=[aql_validator],
    max_retries=2
)
print(f"Query: {query_result.query}")

# Test 2: Generate collection schema
print("\nGenerating collection schema...")
schema_result = completion_with_validation(
    messages=[
        {"role": "user", "content": "Design a user collection schema"}
    ],
    response_format=DocumentSchema,
    validators=[],  # Could add custom schema validator
    max_retries=2
)
print(f"Schema: {json.dumps(schema_result.dict(), indent=2)}")

print("\nIntegration successful!")
```

## Step 7: Environment Setup

Add to your ArangoDB `.env`:

```bash
LITELLM_DEFAULT_MODEL=vertex_ai/gemini-2.5-flash-preview-04-17
ENABLE_LLM_VALIDATION=true
REDIS_HOST=localhost
```

## Summary

The integration provides:
1. Custom AQL validators
2. Type-safe query generation
3. CLI tools for testing
4. Modular architecture
5. Easy extensibility

Ready to use in `/home/graham/workspace/experiments/arangodb/`!