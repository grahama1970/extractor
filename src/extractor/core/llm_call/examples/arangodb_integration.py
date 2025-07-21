"""
Module: arangodb_integration.py

External Dependencies:
- pydantic: https://docs.pydantic.dev/
- marker: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

#!/usr/bin/env python3
"""
Example integration of marker-llm-call validation loops with ArangoDB project.

This demonstrates how to use the validation system in another project context,
specifically with ArangoDB operations.
"""

import json
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from extractor.core.llm_call import completion_with_validation
from extractor.core.llm_call.validators import TableValidator, GeneralContentValidator
from extractor.core.llm_call.base import ValidationStrategy, ValidationResult
from extractor.core.llm_call.decorators import validator


# Define Pydantic models for ArangoDB operations
class ArangoQuery(BaseModel):
    """ArangoDB query structure"""
    query: str = Field(description="AQL query string")
    bind_vars: Optional[Dict[str, Any]] = Field(default={}, description="Bind variables")
    
class ArangoDocument(BaseModel):
    """ArangoDB document structure"""
    _key: Optional[str] = Field(default=None, description="Document key")
    _id: Optional[str] = Field(default=None, description="Document ID")
    _rev: Optional[str] = Field(default=None, description="Document revision")
    data: Dict[str, Any] = Field(description="Document data")

class ArangoCollection(BaseModel):
    """ArangoDB collection metadata"""
    name: str = Field(description="Collection name")
    type: str = Field(default="document", description="Collection type")
    schema: Optional[Dict[str, Any]] = Field(default=None, description="Collection schema")


# Custom validator for ArangoDB queries
@validator("aql")
class AQLValidator(ValidationStrategy):
    """Validator for ArangoDB Query Language (AQL) queries"""
    
    def __init__(self, check_syntax: bool = True, max_complexity: int = 10):
        self.check_syntax = check_syntax
        self.max_complexity = max_complexity
    
    def validate(self, content: Any) -> ValidationResult:
        """Validate AQL query"""
        if not isinstance(content, (str, dict)):
            return ValidationResult(
                valid=False,
                error="Content must be a string or ArangoQuery dict"
            )
        
        # Extract query string
        if isinstance(content, dict):
            query = content.get("query", "")
        else:
            query = content
        
        # Basic validation
        if not query.strip():
            return ValidationResult(
                valid=False,
                error="Query cannot be empty"
            )
        
        # Check for required keywords
        query_upper = query.upper()
        if not any(keyword in query_upper for keyword in ["FOR", "RETURN", "INSERT", "UPDATE", "REMOVE"]):
            return ValidationResult(
                valid=False,
                error="Query must contain at least one AQL operation",
                suggestions=["Add a FOR/RETURN clause", "Add an INSERT/UPDATE/REMOVE operation"]
            )
        
        # Check complexity (simplified)
        complexity = query.count("FOR") + query.count("LET") + query.count("FILTER")
        if complexity > self.max_complexity:
            return ValidationResult(
                valid=False,
                error=f"Query complexity ({complexity}) exceeds maximum ({self.max_complexity})",
                suggestions=["Simplify the query", "Break into multiple queries"]
            )
        
        return ValidationResult(
            valid=True,
            debug_info={"complexity": complexity, "operations": self._extract_operations(query)}
        )
    
    def _extract_operations(self, query: str) -> List[str]:
        """Extract AQL operations from query"""
        operations = []
        for op in ["FOR", "RETURN", "INSERT", "UPDATE", "REMOVE", "FILTER", "SORT", "LIMIT"]:
            if op in query.upper():
                operations.append(op)
        return operations


# Custom validator for ArangoDB documents
@validator("arango_doc")
class ArangoDocumentValidator(ValidationStrategy):
    """Validator for ArangoDB documents"""
    
    def __init__(self, collection_schema: Optional[Dict[str, Any]] = None):
        self.collection_schema = collection_schema
    
    def validate(self, content: Any) -> ValidationResult:
        """Validate ArangoDB document"""
        if not isinstance(content, dict):
            return ValidationResult(
                valid=False,
                error="Document must be a dictionary"
            )
        
        # Check for data field
        if "data" not in content:
            return ValidationResult(
                valid=False,
                error="Document must have a 'data' field"
            )
        
        # Validate against schema if provided
        if self.collection_schema:
            data = content.get("data", {})
            required_fields = self.collection_schema.get("required", [])
            
            missing_fields = [f for f in required_fields if f not in data]
            if missing_fields:
                return ValidationResult(
                    valid=False,
                    error=f"Missing required fields: {missing_fields}",
                    suggestions=[f"Add field: {f}" for f in missing_fields]
                )
        
        return ValidationResult(valid=True)


class ArangoDBAssistant:
    """
    Example class showing how to integrate marker-llm-call with ArangoDB operations.
    """
    
    def __init__(self, model: str = None):
        self.model = model or os.environ.get("LITELLM_DEFAULT_MODEL", "vertex_ai/gemini-1.5-flash")
    
    def generate_aql_query(self, description: str) -> ArangoQuery:
        """Generate an AQL query from natural language description"""
        
        # Create AQL validator
        aql_validator = AQLValidator(check_syntax=True, max_complexity=5)
        
        # Generate query with validation
        result = completion_with_validation(
            messages=[
                {
                    "role": "system",
                    "content": "You are an ArangoDB query expert. Generate AQL queries from descriptions."
                },
                {
                    "role": "user",
                    "content": f"Generate an AQL query for: {description}"
                }
            ],
            response_format=ArangoQuery,
            validators=[aql_validator],
            max_retries=3,
            model=self.model
        )
        
        return result
    
    def create_collection_schema(self, description: str) -> ArangoCollection:
        """Generate a collection schema from description"""
        
        # Use table validator for schema validation
        table_validator = TableValidator(min_rows=1, min_cols=2)
        
        result = completion_with_validation(
            messages=[
                {
                    "role": "system",
                    "content": "You are an ArangoDB schema designer. Create collection schemas."
                },
                {
                    "role": "user",
                    "content": f"Create a collection schema for: {description}"
                }
            ],
            response_format=ArangoCollection,
            validators=[GeneralContentValidator(min_length=10)],
            max_retries=2,
            model=self.model
        )
        
        return result
    
    def optimize_query(self, query: str) -> ArangoQuery:
        """Optimize an existing AQL query"""
        
        # Create validator with stricter complexity limits
        aql_validator = AQLValidator(check_syntax=True, max_complexity=3)
        
        result = completion_with_validation(
            messages=[
                {
                    "role": "system",
                    "content": "You are an AQL optimization expert. Optimize queries for performance."
                },
                {
                    "role": "user",
                    "content": f"Optimize this AQL query:\n{query}"
                }
            ],
            response_format=ArangoQuery,
            validators=[aql_validator],
            max_retries=3,
            model=self.model
        )
        
        return result
    
    def generate_sample_documents(self, collection_schema: Dict[str, Any], count: int = 5) -> List[ArangoDocument]:
        """Generate sample documents based on schema"""
        
        # Create document validator with schema
        doc_validator = ArangoDocumentValidator(collection_schema=collection_schema)
        
        documents = []
        for i in range(count):
            result = completion_with_validation(
                messages=[
                    {
                        "role": "system",
                        "content": "Generate sample ArangoDB documents based on schema."
                    },
                    {
                        "role": "user",
                        "content": f"Generate document {i+1} for schema: {json.dumps(collection_schema)}"
                    }
                ],
                response_format=ArangoDocument,
                validators=[doc_validator],
                max_retries=2,
                model=self.model
            )
            documents.append(result)
        
        return documents


def main():
    """Example usage of ArangoDB integration"""
    
    # Initialize assistant
    assistant = ArangoDBAssistant()
    
    print("=== ArangoDB Integration Example ===\n")
    
    # Example 1: Generate AQL query
    print("1. Generating AQL Query")
    query_description = "Find all users who registered in 2024 and have made more than 5 purchases"
    query = assistant.generate_aql_query(query_description)
    print(f"Description: {query_description}")
    print(f"Generated Query: {query.query}")
    print(f"Bind Variables: {query.bind_vars}")
    print()
    
    # Example 2: Create collection schema
    print("2. Creating Collection Schema")
    schema_description = "User collection with name, email, registration date, and purchase count"
    collection = assistant.create_collection_schema(schema_description)
    print(f"Collection Name: {collection.name}")
    print(f"Collection Type: {collection.type}")
    print(f"Schema: {json.dumps(collection.schema, indent=2)}")
    print()
    
    # Example 3: Optimize query
    print("3. Optimizing Query")
    complex_query = """
    FOR user IN users
        FOR purchase IN purchases
            FILTER purchase.user_id == user._id
            FILTER purchase.amount > 100
            COLLECT u = user WITH COUNT INTO total
            FILTER total > 5
            RETURN {user: u, purchases: total}
    """
    optimized = assistant.optimize_query(complex_query)
    print("Original Query:")
    print(complex_query)
    print("\nOptimized Query:")
    print(optimized.query)
    print()
    
    # Example 4: Generate sample documents
    print("4. Generating Sample Documents")
    sample_schema = {
        "required": ["name", "email", "registration_date"],
        "properties": {
            "name": {"type": "string"},
            "email": {"type": "string"},
            "registration_date": {"type": "string"},
            "purchase_count": {"type": "integer"}
        }
    }
    documents = assistant.generate_sample_documents(sample_schema, count=3)
    for i, doc in enumerate(documents):
        print(f"Document {i+1}:")
        print(json.dumps(doc.data, indent=2))
        print()


if __name__ == "__main__":
    main()