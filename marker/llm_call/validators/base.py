"""Basic validators for common use cases.

This module provides built-in validators that cover common validation scenarios.
"""

import re
from typing import Any, Dict, List, Optional

from marker.llm_call.core.base import BaseValidator, ValidationResult
from marker.llm_call.core.strategies import validator


@validator("field_presence")
class FieldPresenceValidator(BaseValidator):
    """Validates that required fields are present and non-empty."""
    
    def __init__(self, required_fields: List[str]):
        """Initialize validator.
        
        Args:
            required_fields: List of field names that must be present
        """
        super().__init__(required_fields=required_fields)
        self.required_fields = required_fields
    
    @property
    def name(self) -> str:
        return f"field_presence({','.join(self.required_fields)})"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate that required fields are present."""
        # Handle both dictionary and object responses
        if hasattr(response, '__dict__'):
            data = response.__dict__
        elif isinstance(response, dict):
            data = response
        else:
            return ValidationResult(
                valid=False,
                error=f"Response is not a dictionary or object: {type(response)}"
            )
        
        missing_fields = []
        empty_fields = []
        
        for field in self.required_fields:
            if field not in data:
                missing_fields.append(field)
            elif data[field] is None or (isinstance(data[field], str) and not data[field].strip()):
                empty_fields.append(field)
        
        errors = []
        suggestions = []
        
        if missing_fields:
            errors.append(f"Missing required fields: {', '.join(missing_fields)}")
            suggestions.extend([f"Add field '{field}' to response" for field in missing_fields])
        
        if empty_fields:
            errors.append(f"Empty required fields: {', '.join(empty_fields)}")
            suggestions.extend([f"Provide value for field '{field}'" for field in empty_fields])
        
        if errors:
            return ValidationResult(
                valid=False,
                error="; ".join(errors),
                suggestions=suggestions,
                debug_info={"missing": missing_fields, "empty": empty_fields}
            )
        
        return ValidationResult(valid=True)


@validator("length_check")
class LengthValidator(BaseValidator):
    """Validates field length constraints."""
    
    def __init__(self, field_name: str, min_length: Optional[int] = None, max_length: Optional[int] = None):
        """Initialize validator.
        
        Args:
            field_name: Name of the field to check
            min_length: Minimum allowed length
            max_length: Maximum allowed length
        """
        super().__init__(field_name=field_name, min_length=min_length, max_length=max_length)
        self.field_name = field_name
        self.min_length = min_length
        self.max_length = max_length
    
    @property
    def name(self) -> str:
        constraints = []
        if self.min_length is not None:
            constraints.append(f"min={self.min_length}")
        if self.max_length is not None:
            constraints.append(f"max={self.max_length}")
        return f"length_check({self.field_name},{','.join(constraints)})"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate field length."""
        # Extract field value
        if hasattr(response, self.field_name):
            value = getattr(response, self.field_name)
        elif isinstance(response, dict) and self.field_name in response:
            value = response[self.field_name]
        else:
            return ValidationResult(
                valid=False,
                error=f"Field '{self.field_name}' not found in response"
            )
        
        # Check if value is string or has length
        if isinstance(value, str):
            length = len(value)
        elif hasattr(value, '__len__'):
            length = len(value)
        else:
            return ValidationResult(
                valid=False,
                error=f"Field '{self.field_name}' does not have a length property"
            )
        
        errors = []
        suggestions = []
        
        if self.min_length is not None and length < self.min_length:
            errors.append(f"Field '{self.field_name}' is too short: {length} < {self.min_length}")
            suggestions.append(f"Expand '{self.field_name}' to at least {self.min_length} characters")
        
        if self.max_length is not None and length > self.max_length:
            errors.append(f"Field '{self.field_name}' is too long: {length} > {self.max_length}")
            suggestions.append(f"Reduce '{self.field_name}' to at most {self.max_length} characters")
        
        if errors:
            return ValidationResult(
                valid=False,
                error="; ".join(errors),
                suggestions=suggestions,
                debug_info={"field": self.field_name, "length": length}
            )
        
        return ValidationResult(
            valid=True,
            debug_info={"field": self.field_name, "length": length}
        )


@validator("format_check")
class FormatValidator(BaseValidator):
    """Validates field format using regular expressions."""
    
    def __init__(self, field_name: str, pattern: str, description: Optional[str] = None):
        """Initialize validator.
        
        Args:
            field_name: Name of the field to check
            pattern: Regular expression pattern
            description: Human-readable description of the format
        """
        super().__init__(field_name=field_name, pattern=pattern, description=description)
        self.field_name = field_name
        self.pattern = pattern
        self.description = description or f"match pattern {pattern}"
        self._compiled_pattern = re.compile(pattern)
    
    @property
    def name(self) -> str:
        return f"format_check({self.field_name})"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate field format."""
        # Extract field value
        if hasattr(response, self.field_name):
            value = getattr(response, self.field_name)
        elif isinstance(response, dict) and self.field_name in response:
            value = response[self.field_name]
        else:
            return ValidationResult(
                valid=False,
                error=f"Field '{self.field_name}' not found in response"
            )
        
        # Convert to string if needed
        value_str = str(value) if value is not None else ""
        
        if not self._compiled_pattern.match(value_str):
            return ValidationResult(
                valid=False,
                error=f"Field '{self.field_name}' does not {self.description}",
                suggestions=[f"Format '{self.field_name}' to {self.description}"],
                debug_info={
                    "field": self.field_name,
                    "value": value_str,
                    "pattern": self.pattern
                }
            )
        
        return ValidationResult(
            valid=True,
            debug_info={"field": self.field_name, "value": value_str}
        )


@validator("type_check")
class TypeValidator(BaseValidator):
    """Validates field types."""
    
    def __init__(self, field_name: str, expected_type: type):
        """Initialize validator.
        
        Args:
            field_name: Name of the field to check
            expected_type: Expected type of the field
        """
        super().__init__(field_name=field_name, expected_type=expected_type)
        self.field_name = field_name
        self.expected_type = expected_type
    
    @property
    def name(self) -> str:
        return f"type_check({self.field_name},{self.expected_type.__name__})"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate field type."""
        # Extract field value
        if hasattr(response, self.field_name):
            value = getattr(response, self.field_name)
        elif isinstance(response, dict) and self.field_name in response:
            value = response[self.field_name]
        else:
            return ValidationResult(
                valid=False,
                error=f"Field '{self.field_name}' not found in response"
            )
        
        if not isinstance(value, self.expected_type):
            actual_type = type(value).__name__
            return ValidationResult(
                valid=False,
                error=f"Field '{self.field_name}' has wrong type: expected {self.expected_type.__name__}, got {actual_type}",
                suggestions=[f"Convert '{self.field_name}' to {self.expected_type.__name__}"],
                debug_info={
                    "field": self.field_name,
                    "expected_type": self.expected_type.__name__,
                    "actual_type": actual_type
                }
            )
        
        return ValidationResult(
            valid=True,
            debug_info={
                "field": self.field_name,
                "type": type(value).__name__
            }
        )


@validator("range_check")
class RangeValidator(BaseValidator):
    """Validates numeric values are within a range."""
    
    def __init__(self, field_name: str, min_value: Optional[float] = None, max_value: Optional[float] = None):
        """Initialize validator.
        
        Args:
            field_name: Name of the field to check
            min_value: Minimum allowed value
            max_value: Maximum allowed value
        """
        super().__init__(field_name=field_name, min_value=min_value, max_value=max_value)
        self.field_name = field_name
        self.min_value = min_value
        self.max_value = max_value
    
    @property
    def name(self) -> str:
        constraints = []
        if self.min_value is not None:
            constraints.append(f"min={self.min_value}")
        if self.max_value is not None:
            constraints.append(f"max={self.max_value}")
        return f"range_check({self.field_name},{','.join(constraints)})"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate numeric range."""
        # Extract field value
        if hasattr(response, self.field_name):
            value = getattr(response, self.field_name)
        elif isinstance(response, dict) and self.field_name in response:
            value = response[self.field_name]
        else:
            return ValidationResult(
                valid=False,
                error=f"Field '{self.field_name}' not found in response"
            )
        
        # Check if value is numeric
        if not isinstance(value, (int, float)):
            return ValidationResult(
                valid=False,
                error=f"Field '{self.field_name}' is not numeric: {type(value).__name__}"
            )
        
        errors = []
        suggestions = []
        
        if self.min_value is not None and value < self.min_value:
            errors.append(f"Field '{self.field_name}' is too small: {value} < {self.min_value}")
            suggestions.append(f"Increase '{self.field_name}' to at least {self.min_value}")
        
        if self.max_value is not None and value > self.max_value:
            errors.append(f"Field '{self.field_name}' is too large: {value} > {self.max_value}")
            suggestions.append(f"Reduce '{self.field_name}' to at most {self.max_value}")
        
        if errors:
            return ValidationResult(
                valid=False,
                error="; ".join(errors),
                suggestions=suggestions,
                debug_info={"field": self.field_name, "value": value}
            )
        
        return ValidationResult(
            valid=True,
            debug_info={"field": self.field_name, "value": value}
        )