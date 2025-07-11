"""LLM Call Module for Marker.
Module: __init__.py
Description: Package initialization and exports

Provides advanced validation loop functionality for LLM calls with retry logic and custom validation strategies.
"""

__version__ = "0.1.0"

from extractor.core.llm_call.core.base import ValidationResult, ValidationStrategy
from extractor.core.llm_call.core.retry import retry_with_validation, RetryConfig
from extractor.core.llm_call.core.strategies import registry, validator

__all__ = [
    "ValidationResult",
    "ValidationStrategy",
    "retry_with_validation",
    "RetryConfig",
    "registry",
    "validator",
]
