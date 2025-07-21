# ArangoDB Integration Example

This example demonstrates how to integrate the marker-llm-call validation system with ArangoDB operations in another project.

## Overview

The `arangodb_integration.py` example shows:
1. Creating custom validators for ArangoDB-specific content
2. Generating valid AQL queries with validation
3. Creating collection schemas
4. Optimizing existing queries
5. Generating sample documents

## Key Features

### Custom Validators

1. **AQLValidator**: Validates ArangoDB Query Language (AQL) queries
   - Checks syntax and required keywords
   - Limits query complexity
   - Provides helpful suggestions

2. **ArangoDocumentValidator**: Validates ArangoDB documents
   - Ensures required fields are present
   - Validates against collection schema
   - Checks document structure

### Integration Pattern

```python
from marker.llm_call import completion_with_validation
from marker.llm_call.decorators import validator

# Define custom validator
@validator("aql")
class AQLValidator(ValidationStrategy):
    def validate(self, content: Any) -> ValidationResult:
        # Custom validation logic
        ...

# Use in LLM call
result = completion_with_validation(
    messages=[...],
    response_format=ArangoQuery,
    validators=[AQLValidator()],
    max_retries=3
)
```

## Usage

### Basic Example

```python
from arangodb_integration import ArangoDBAssistant

# Initialize assistant
assistant = ArangoDBAssistant()

# Generate AQL query
query = assistant.generate_aql_query(
    "Find all users who registered in 2024"
)
print(query.query)  # FOR u IN users FILTER u.registration_date >= "2024-01-01" RETURN u
```

### Advanced Usage

```python
# Create collection schema
collection = assistant.create_collection_schema(
    "User collection with profile data"
)

# Generate sample documents
documents = assistant.generate_sample_documents(
    collection.schema, 
    count=5
)

# Optimize complex query
optimized = assistant.optimize_query(complex_query)
```

## Running the Example

1. Install dependencies:
   ```bash
   pip install marker-llm-call
   ```

2. Set environment variables:
   ```bash
   export LITELLM_DEFAULT_MODEL="vertex_ai/gemini-1.5-flash"
   ```

3. Run the example:
   ```bash
   python arangodb_integration.py
   ```

## Output Example

```
=== ArangoDB Integration Example ===

1. Generating AQL Query
Description: Find all users who registered in 2024 and have made more than 5 purchases
Generated Query: FOR u IN users FILTER u.registration_date >= "2024-01-01" AND u.purchase_count > 5 RETURN u
Bind Variables: {}

2. Creating Collection Schema
Collection Name: users
Collection Type: document
Schema: {
  "required": ["name", "email", "registration_date"],
  "properties": {
    "name": {"type": "string"},
    "email": {"type": "string"},
    "registration_date": {"type": "string"},
    "purchase_count": {"type": "integer"}
  }
}

3. Optimizing Query
Original Query:
    FOR user IN users
        FOR purchase IN purchases
            FILTER purchase.user_id == user._id
            FILTER purchase.amount > 100
            COLLECT u = user WITH COUNT INTO total
            FILTER total > 5
            RETURN {user: u, purchases: total}

Optimized Query:
FOR u IN users
  LET purchases = (
    FOR p IN purchases
    FILTER p.user_id == u._id AND p.amount > 100
    RETURN 1
  )
  LET total = LENGTH(purchases)
  FILTER total > 5
  RETURN {user: u, purchases: total}

4. Generating Sample Documents
Document 1:
{
  "name": "John Doe",
  "email": "john@example.com",
  "registration_date": "2024-01-15",
  "purchase_count": 8
}
...
```

## Integration Benefits

1. **Type Safety**: Pydantic models ensure correct data structures
2. **Validation**: Custom validators prevent invalid queries
3. **Retry Logic**: Automatic retries with different approaches
4. **Error Handling**: Clear error messages and suggestions
5. **Extensibility**: Easy to add new validators

## Extending the Example

### Adding New Validators

```python
@validator("arango_index")
class ArangoIndexValidator(ValidationStrategy):
    """Validator for ArangoDB index definitions"""
    
    def validate(self, content: Any) -> ValidationResult:
        # Validate index structure
        if not isinstance(content, dict):
            return ValidationResult(
                valid=False,
                error="Index must be a dictionary"
            )
        
        # Check required fields
        if "type" not in content or "fields" not in content:
            return ValidationResult(
                valid=False,
                error="Index must have 'type' and 'fields'",
                suggestions=["Add index type", "Specify indexed fields"]
            )
        
        return ValidationResult(valid=True)
```

### Integrating with Real ArangoDB

```python
from arango import ArangoClient

class ArangoDBIntegration(ArangoDBAssistant):
    def __init__(self, db_url: str, username: str, password: str):
        super().__init__()
        self.client = ArangoClient(hosts=db_url)
        self.db = self.client.db(
            name="_system",
            username=username,
            password=password
        )
    
    def execute_validated_query(self, description: str):
        """Generate and execute a validated query"""
        # Generate query with validation
        query = self.generate_aql_query(description)
        
        # Execute in database
        cursor = self.db.aql.execute(
            query.query,
            bind_vars=query.bind_vars
        )
        
        return list(cursor)
```

## Best Practices

1. **Custom Validators**: Create domain-specific validators
2. **Error Recovery**: Use suggestions for better retry logic
3. **Type Safety**: Use Pydantic models for all data structures
4. **Incremental Validation**: Validate at each step
5. **Logging**: Enable debug logging for troubleshooting

## See Also

- [Validators Documentation](../docs/validators.md)
- [API Reference](../docs/api_reference.md)
- [Examples](../docs/examples.md)
- [Architecture](../docs/architecture.md)