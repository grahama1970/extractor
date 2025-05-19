"""Base classes and protocols for LLM validation.

This module defines the core interfaces for the validation system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    
    valid: bool
    error: Optional[str] = None
    debug_info: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None
    
    def __str__(self) -> str:
        if self.valid:
            return "Validation passed"
        return f"Validation failed: {self.error}"
    
    def __repr__(self) -> str:
        return f"ValidationResult(valid={self.valid}, error={self.error})"


@runtime_checkable
class ValidationStrategy(Protocol):
    """Protocol for validation strategies.
    
    Any class implementing this protocol can be used as a validation strategy.
    This allows for maximum flexibility in creating custom validators.
    """
    
    @property
    def name(self) -> str:
        """Strategy name for debugging and logging."""
        ...
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate the response.
        
        Args:
            response: The LLM response to validate
            context: Additional context for validation (e.g., attempt number, prompt)
            
        Returns:
            ValidationResult indicating success or failure with details
        """
        ...


@runtime_checkable
class AsyncValidationStrategy(Protocol):
    """Protocol for async validation strategies."""
    
    @property
    def name(self) -> str:
        """Strategy name for debugging and logging."""
        ...
    
    async def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate the response asynchronously.
        
        Args:
            response: The LLM response to validate
            context: Additional context for validation
            
        Returns:
            ValidationResult indicating success or failure
        """
        ...


class BaseValidator(ABC):
    """Abstract base class for validators.
    
    Provides common functionality and ensures consistent interface.
    """
    
    def __init__(self, **kwargs):
        """Initialize validator with optional configuration."""
        self.config = kwargs
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the validator name."""
        pass
    
    @abstractmethod
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate the response."""
        pass
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"