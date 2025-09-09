#!/usr/bin/env python3
"""
Enhanced error handling with retry logic for the PDF extraction pipeline.

Provides structured exceptions, retry decorators, and comprehensive error tracking.
"""

import traceback
import asyncio
from typing import Optional, Dict, Any, Callable, Type
from functools import wraps
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential,
    retry_if_exception_type,
    before_retry,
    after_retry
)
from loguru import logger
import time


# Custom Exceptions
class PDFExtractionError(Exception):
    """Base exception for PDF extraction errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}
        self.timestamp = time.time()


class AnnotationExtractionError(PDFExtractionError):
    """Raised when annotation extraction fails."""
    pass


class SecurityError(PDFExtractionError):
    """Raised when security validation fails."""
    pass


class ResourceLimitError(PDFExtractionError):
    """Raised when resource limits are exceeded."""
    pass


class DatabaseConnectionError(PDFExtractionError):
    """Raised when database operations fail."""
    pass


class LLMProcessingError(PDFExtractionError):
    """Raised when LLM processing fails."""
    pass


class ValidationError(PDFExtractionError):
    """Raised when validation fails."""
    pass


# Retry callbacks
def log_retry_attempt(retry_state):
    """Log retry attempts."""
    logger.warning(
        f"Retrying {retry_state.fn.__name__} "
        f"(attempt {retry_state.attempt_number}) "
        f"after {retry_state.outcome.exception()}"
    )


def log_retry_success(retry_state):
    """Log successful retry."""
    logger.info(
        f"Retry successful for {retry_state.fn.__name__} "
        f"after {retry_state.attempt_number} attempts"
    )


# Retry decorators
def retry_on_network_error(
    max_attempts: int = 3,
    wait_min: float = 4.0,
    wait_max: float = 10.0
):
    """Retry decorator for network operations."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=wait_min, max=wait_max),
        retry=retry_if_exception_type((
            ConnectionError,
            DatabaseConnectionError,
            TimeoutError
        )),
        before=log_retry_attempt,
        after=log_retry_success,
        reraise=True
    )


def retry_on_llm_error(
    max_attempts: int = 3,
    wait_min: float = 2.0,
    wait_max: float = 60.0
):
    """Retry decorator for LLM operations with backoff."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=2, min=wait_min, max=wait_max),
        retry=retry_if_exception_type((
            LLMProcessingError,
            TimeoutError
        )),
        before=log_retry_attempt,
        after=log_retry_success,
        reraise=True
    )


# Error context manager
class ErrorHandler:
    """Context manager for comprehensive error handling."""
    
    def __init__(
        self, 
        operation: str,
        raise_on_error: bool = True,
        default_return: Any = None
    ):
        """Initialize error handler.
        
        Args:
            operation: Description of the operation
            raise_on_error: Whether to raise exceptions
            default_return: Default value to return on error
        """
        self.operation = operation
        self.raise_on_error = raise_on_error
        self.default_return = default_return
        self.start_time = None
        
    def __enter__(self):
        """Enter context."""
        self.start_time = time.time()
        logger.debug(f"Starting operation: {self.operation}")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context with error handling."""
        elapsed = time.time() - self.start_time
        
        if exc_type is None:
            logger.debug(f"Operation completed: {self.operation} ({elapsed:.2f}s)")
            return False
        
        # Log the error with context
        error_details = {
            'operation': self.operation,
            'error_type': exc_type.__name__,
            'error_message': str(exc_val),
            'elapsed_time': elapsed,
            'traceback': traceback.format_exc()
        }
        
        logger.error(
            f"Operation failed: {self.operation} - "
            f"{exc_type.__name__}: {exc_val}"
        )
        logger.debug(f"Error details: {error_details}")
        
        # Convert to appropriate exception type
        if isinstance(exc_val, PDFExtractionError):
            # Already our exception type
            if self.raise_on_error:
                return False
        else:
            # Wrap in our exception type
            wrapped = PDFExtractionError(
                f"{self.operation} failed: {exc_val}",
                details=error_details
            )
            if self.raise_on_error:
                raise wrapped from exc_val
        
        # Suppress exception if not raising
        return True


# Async error handler
class AsyncErrorHandler:
    """Async context manager for error handling."""
    
    def __init__(
        self,
        operation: str,
        raise_on_error: bool = True,
        default_return: Any = None
    ):
        """Initialize async error handler."""
        self.operation = operation
        self.raise_on_error = raise_on_error
        self.default_return = default_return
        self.start_time = None
    
    async def __aenter__(self):
        """Enter async context."""
        self.start_time = time.time()
        logger.debug(f"Starting async operation: {self.operation}")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context with error handling."""
        elapsed = time.time() - self.start_time
        
        if exc_type is None:
            logger.debug(f"Async operation completed: {self.operation} ({elapsed:.2f}s)")
            return False
        
        # Log the error
        logger.error(
            f"Async operation failed: {self.operation} - "
            f"{exc_type.__name__}: {exc_val}"
        )
        
        if not self.raise_on_error:
            return True
        
        return False


# Validation decorators
def validate_input(**validations):
    """Decorator to validate function inputs."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get function signature
            import inspect
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            
            # Validate each parameter
            for param_name, validator in validations.items():
                if param_name in bound.arguments:
                    value = bound.arguments[param_name]
                    
                    if not validator(value):
                        raise ValidationError(
                            f"Invalid {param_name}: {value} failed validation"
                        )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Common validators
def not_none(value) -> bool:
    """Validate value is not None."""
    return value is not None


def is_positive(value) -> bool:
    """Validate value is positive."""
    return value is not None and value > 0


def is_valid_path(value) -> bool:
    """Validate value is a valid path."""
    if value is None:
        return False
    try:
        from pathlib import Path
        Path(value).resolve()
        return True
    except:
        return False


# Error aggregator for batch operations
class ErrorAggregator:
    """Collect and analyze errors from batch operations."""
    
    def __init__(self, operation: str):
        """Initialize error aggregator."""
        self.operation = operation
        self.errors = []
        self.successes = 0
        self.start_time = time.time()
    
    def add_error(self, item_id: str, error: Exception):
        """Add an error to the collection."""
        self.errors.append({
            'item_id': item_id,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': time.time()
        })
    
    def add_success(self):
        """Increment success counter."""
        self.successes += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Get error summary."""
        total = self.successes + len(self.errors)
        elapsed = time.time() - self.start_time
        
        # Group errors by type
        error_types = {}
        for error in self.errors:
            error_type = error['error_type']
            if error_type not in error_types:
                error_types[error_type] = 0
            error_types[error_type] += 1
        
        return {
            'operation': self.operation,
            'total_items': total,
            'successes': self.successes,
            'failures': len(self.errors),
            'success_rate': self.successes / total if total > 0 else 0,
            'elapsed_time': elapsed,
            'error_types': error_types,
            'errors': self.errors[:10]  # First 10 errors
        }
    
    def raise_if_failed(self, threshold: float = 0.5):
        """Raise exception if failure rate exceeds threshold."""
        total = self.successes + len(self.errors)
        if total == 0:
            return
        
        failure_rate = len(self.errors) / total
        if failure_rate > threshold:
            summary = self.get_summary()
            raise PDFExtractionError(
                f"Batch operation '{self.operation}' failed: "
                f"{len(self.errors)}/{total} items failed "
                f"({failure_rate:.1%} failure rate)",
                details=summary
            )