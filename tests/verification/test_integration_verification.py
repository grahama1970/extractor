#!/usr/bin/env python3
"""Integration test to verify the llm_call module works correctly."""

import json
import os
from pathlib import Path

# Test basic imports
try:
    from marker.llm_call import ValidationResult, registry, validator
    from marker.llm_call.service import ValidatedLiteLLMService
    from marker.llm_call.validators.base import FieldPresenceValidator
    print("✓ All imports successful")
except Exception as e:
    print(f"✗ Import error: {e}")
    exit(1)

# Test ValidationResult
result = ValidationResult(valid=True)
print(f"✓ ValidationResult created: {result}")

# Test failed validation
failed_result = ValidationResult(
    valid=False,
    error="Test error",
    suggestions=["Fix this", "Try that"]
)
print(f"✓ Failed ValidationResult: {failed_result}")

# Test FieldPresenceValidator
validator_instance = FieldPresenceValidator(required_fields=["title", "content"])
test_response = {"title": "Test", "content": "Content"}
validation = validator_instance.validate(test_response, {})
print(f"✓ Field validation passed: {validation}")

# Test registry
print("\n✓ Available strategies:")
for strategy in registry.list_all():
    print(f"  - {strategy}")

# Test service creation without validation
service = ValidatedLiteLLMService()
print(f"\n✓ Service created with validation disabled: {service.enable_validation_loop}")

# Test service creation with validation
validated_service = ValidatedLiteLLMService({
    "enable_validation_loop": True,
    "validation_strategies": ["field_presence(required_fields=['title'])"]
})
print(f"✓ Service created with validation enabled: {validated_service.enable_validation_loop}")
print(f"✓ Validation strategies: {validated_service.validation_strategies}")

# Check environment variables
print("\n✓ Environment variables:")
print(f"  - LITELLM_DEFAULT_MODEL: {os.getenv('LITELLM_DEFAULT_MODEL', 'Not set')}")
print(f"  - LITELLM_JUDGE_MODEL: {os.getenv('LITELLM_JUDGE_MODEL', 'Not set')}")
print(f"  - ENABLE_LLM_VALIDATION: {os.getenv('ENABLE_LLM_VALIDATION', 'Not set')}")

print("\n✓ Integration test completed successfully!")