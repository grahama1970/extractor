"""Test the LLM call module functionality."""

import os
from pathlib import Path

import pytest
from pydantic import BaseModel

from marker.llm_call import ValidationResult, registry
from marker.llm_call.service import ValidatedLiteLLMService
from marker.schema.blocks import Block
from marker.llm_call.validators.base import FieldPresenceValidator


class TestResponse(BaseModel):
    """Test response model."""
    title: str
    description: str
    count: int


def test_validation_result():
    """Test ValidationResult class."""
    # Test successful validation
    result = ValidationResult(valid=True)
    assert result.valid
    assert str(result) == "Validation passed"
    
    # Test failed validation
    result = ValidationResult(
        valid=False,
        error="Test error",
        suggestions=["Fix this", "Try that"]
    )
    assert not result.valid
    assert "Test error" in str(result)
    assert result.suggestions == ["Fix this", "Try that"]


def test_field_presence_validator():
    """Test FieldPresenceValidator."""
    validator = FieldPresenceValidator(required_fields=["title", "description"])
    
    # Test with valid response
    valid_response = {
        "title": "Test Title",
        "description": "Test Description"
    }
    result = validator.validate(valid_response, {})
    assert result.valid
    
    # Test with missing field
    invalid_response = {
        "title": "Test Title"
    }
    result = validator.validate(invalid_response, {})
    assert not result.valid
    assert "Missing required fields: description" in result.error
    
    # Test with empty field
    empty_response = {
        "title": "Test Title",
        "description": ""
    }
    result = validator.validate(empty_response, {})
    assert not result.valid
    assert "Empty required fields: description" in result.error


def test_strategy_registry():
    """Test strategy registry functionality."""
    # Test listing strategies
    strategies = registry.list_all()
    assert isinstance(strategies, list)
    
    # Test getting a registered strategy
    strategy = registry.get("field_presence", required_fields=["test"])
    assert strategy is not None
    assert hasattr(strategy, "validate")


def test_validated_service_backward_compatibility():
    """Test that ValidatedLiteLLMService maintains backward compatibility."""
    # Create service with validation disabled (default)
    service = ValidatedLiteLLMService()
    
    # Verify validation is disabled by default
    assert not service.enable_validation_loop
    
    # Verify it has all the methods from parent
    assert hasattr(service, "get_api_key")
    assert hasattr(service, "prepare_images")
    assert hasattr(service, "__call__")


def test_validated_service_with_validation():
    """Test ValidatedLiteLLMService with validation enabled."""
    # Create service with validation enabled
    service = ValidatedLiteLLMService({
        "enable_validation_loop": True,
        "validation_strategies": ["field_presence(required_fields=['title'])"],
    })
    
    assert service.enable_validation_loop
    assert service.validation_strategies == ["field_presence(required_fields=['title'])"]
    
    # Test strategy parsing
    strategies = service._get_validation_strategies()
    assert len(strategies) > 0


def test_environment_variable_loading():
    """Test that environment variables are loaded correctly."""
    # Set test environment variables
    os.environ["LITELLM_DEFAULT_MODEL"] = "test/model"
    os.environ["LITELLM_JUDGE_MODEL"] = "test/judge"
    os.environ["ENABLE_LLM_VALIDATION"] = "true"
    
    try:
        service = ValidatedLiteLLMService()
        assert service.default_model == "test/model"
        assert service.judge_model == "test/judge"
        assert service.enable_validation_loop
    finally:
        # Clean up
        del os.environ["LITELLM_DEFAULT_MODEL"]
        del os.environ["LITELLM_JUDGE_MODEL"]
        os.environ["ENABLE_LLM_VALIDATION"] = "false"


if __name__ == "__main__":
    # Run basic tests
    test_validation_result()
    test_field_presence_validator()
    test_strategy_registry()
    test_validated_service_backward_compatibility()
    test_validated_service_with_validation()
    test_environment_variable_loading()
    print("All tests passed!")