"""
Integration tests for ArangoDB validation example.
"""

import pytest
import json
from marker.llm_call.examples.arangodb_integration import (
    AQLValidator,
    ArangoDocumentValidator,
    ArangoDBAssistant,
    ArangoQuery,
    ArangoDocument,
    ArangoCollection
)
from marker.llm_call.base import ValidationResult


class TestAQLValidator:
    """Test AQL query validator"""
    
    def test_valid_query(self):
        """Test validation of valid AQL query"""
        validator = AQLValidator()
        
        # Valid simple query
        result = validator.validate("FOR u IN users RETURN u")
        assert result.valid
        assert "FOR" in result.debug_info["operations"]
        assert "RETURN" in result.debug_info["operations"]
    
    def test_invalid_query_empty(self):
        """Test validation of empty query"""
        validator = AQLValidator()
        
        result = validator.validate("")
        assert not result.valid
        assert "empty" in result.error.lower()
    
    def test_invalid_query_no_operations(self):
        """Test validation of query without operations"""
        validator = AQLValidator()
        
        result = validator.validate("SELECT * FROM users")  # SQL, not AQL
        assert not result.valid
        assert "AQL operation" in result.error
    
    def test_complex_query(self):
        """Test validation of complex query"""
        validator = AQLValidator(max_complexity=3)
        
        # Query with complexity 4 (too complex)
        complex_query = """
        FOR u IN users
            LET purchases = (FOR p IN purchases FILTER p.user_id == u._id RETURN p)
            LET total = SUM(FOR p IN purchases RETURN p.amount)
            FILTER total > 1000
            RETURN {user: u, total: total}
        """
        
        result = validator.validate(complex_query)
        assert not result.valid
        assert "complexity" in result.error.lower()
    
    def test_query_from_dict(self):
        """Test validation of query from dictionary"""
        validator = AQLValidator()
        
        query_dict = {
            "query": "FOR u IN users FILTER u.age > 18 RETURN u",
            "bind_vars": {"min_age": 18}
        }
        
        result = validator.validate(query_dict)
        assert result.valid


class TestArangoDocumentValidator:
    """Test ArangoDB document validator"""
    
    def test_valid_document(self):
        """Test validation of valid document"""
        validator = ArangoDocumentValidator()
        
        doc = {
            "data": {
                "name": "John Doe",
                "email": "john@example.com"
            }
        }
        
        result = validator.validate(doc)
        assert result.valid
    
    def test_invalid_document_no_data(self):
        """Test validation of document without data field"""
        validator = ArangoDocumentValidator()
        
        doc = {"name": "John Doe"}  # Missing 'data' wrapper
        
        result = validator.validate(doc)
        assert not result.valid
        assert "data" in result.error
    
    def test_document_with_schema(self):
        """Test validation against schema"""
        schema = {
            "required": ["name", "email"],
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"}
            }
        }
        validator = ArangoDocumentValidator(collection_schema=schema)
        
        # Valid document
        valid_doc = {
            "data": {
                "name": "John Doe",
                "email": "john@example.com"
            }
        }
        result = validator.validate(valid_doc)
        assert result.valid
        
        # Invalid document (missing required field)
        invalid_doc = {
            "data": {
                "name": "John Doe"
            }
        }
        result = validator.validate(invalid_doc)
        assert not result.valid
        assert "email" in result.error


class TestArangoDBAssistant:
    """Test ArangoDB assistant functionality"""
    
    @pytest.fixture
    def assistant(self):
        """Create assistant instance"""
        return ArangoDBAssistant()
    
    def test_query_generation_structure(self):
        """Test that generated queries have correct structure"""
        # This test verifies the structure without making actual LLM calls
        query = ArangoQuery(
            query="FOR u IN users RETURN u",
            bind_vars={}
        )
        
        assert isinstance(query.query, str)
        assert isinstance(query.bind_vars, dict)
        assert len(query.query) > 0
    
    def test_collection_schema_structure(self):
        """Test collection schema structure"""
        collection = ArangoCollection(
            name="users",
            type="document",
            schema={
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"}
                }
            }
        )
        
        assert collection.name == "users"
        assert collection.type == "document"
        assert "required" in collection.schema
        assert "properties" in collection.schema
    
    def test_document_structure(self):
        """Test document structure"""
        doc = ArangoDocument(
            data={
                "name": "Test User",
                "email": "test@example.com"
            }
        )
        
        assert "name" in doc.data
        assert "email" in doc.data
        assert doc.data["name"] == "Test User"


@pytest.mark.integration
class TestArangoDBIntegration:
    """Integration tests that require LLM service"""
    
    @pytest.fixture
    def assistant(self):
        """Create assistant instance"""
        # This will use the configured LLM service
        return ArangoDBAssistant()
    
    def test_generate_simple_query(self, assistant):
        """Test generating a simple AQL query"""
        # Skip if no LLM service is configured
        import os
        if not os.environ.get("LITELLM_DEFAULT_MODEL"):
            pytest.skip("No LLM model configured")
        
        query = assistant.generate_aql_query("Find all users")
        
        assert isinstance(query, ArangoQuery)
        assert "users" in query.query.lower()
        assert any(op in query.query.upper() for op in ["FOR", "RETURN"])
    
    def test_create_collection_schema(self, assistant):
        """Test creating a collection schema"""
        import os
        if not os.environ.get("LITELLM_DEFAULT_MODEL"):
            pytest.skip("No LLM model configured")
        
        collection = assistant.create_collection_schema(
            "Simple user collection with name and email"
        )
        
        assert isinstance(collection, ArangoCollection)
        assert collection.name
        assert collection.type in ["document", "edge"]


def test_imports():
    """Test that all imports work correctly"""
    from marker.llm_call.examples.arangodb_integration import (
        AQLValidator,
        ArangoDocumentValidator,
        ArangoDBAssistant
    )
    
    assert AQLValidator is not None
    assert ArangoDocumentValidator is not None
    assert ArangoDBAssistant is not None