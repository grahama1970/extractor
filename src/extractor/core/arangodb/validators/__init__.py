"""
Validation utilities for QA generation with ArangoDB integration.
Module: __init__.py
Description: Package initialization and exports

This package provides validation utilities for QA pairs generated from
Marker documents stored in ArangoDB, ensuring they meet quality, relevance,
and accuracy standards for fine-tuning language models.
"""

from extractor.core.arangodb.validators.qa_validator import (
    validate_qa_pairs,
    generate_validation_report,
    DEFAULT_VALIDATION_CHECKS,
    DEFAULT_RELEVANCE_THRESHOLD,
    DEFAULT_ACCURACY_THRESHOLD,
    DEFAULT_QUESTION_QUALITY_THRESHOLD
)

__all__ = [
    'validate_qa_pairs',
    'generate_validation_report',
    'DEFAULT_VALIDATION_CHECKS',
    'DEFAULT_RELEVANCE_THRESHOLD',
    'DEFAULT_ACCURACY_THRESHOLD',
    'DEFAULT_QUESTION_QUALITY_THRESHOLD'
]