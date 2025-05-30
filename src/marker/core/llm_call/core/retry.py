"""Retry mechanism with validation for LLM calls.

This module provides the core retry logic that integrates with validation strategies.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import litellm
from litellm import completion
from loguru import logger
from pydantic import BaseModel

from marker.core.llm_call.core.base import ValidationResult, ValidationStrategy
from marker.core.services.utils.litellm_cache import initialize_litellm_cache


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    
    max_attempts: int = 3
    backoff_factor: float = 2.0
    initial_delay: float = 1.0
    max_delay: float = 60.0
    debug_mode: bool = False
    enable_cache: bool = True
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for next retry attempt."""
        delay = self.initial_delay * (self.backoff_factor ** attempt)
        return min(delay, self.max_delay)


async def retry_with_validation(
    llm_call: Callable,
    messages: List[Dict[str, str]],
    response_format: Optional[BaseModel],
    validation_strategies: List[ValidationStrategy],
    config: RetryConfig = None,
    **kwargs
) -> Any:
    """Retry LLM calls with validation.
    
    Args:
        llm_call: The LLM completion function to call
        messages: List of messages for the conversation
        response_format: Optional Pydantic model for structured outputs
        validation_strategies: List of validation strategies to apply
        config: Retry configuration
        **kwargs: Additional arguments passed to llm_call
    
    Returns:
        The validated LLM response
        
    Raises:
        Exception: If all retry attempts fail
    """
    if config is None:
        config = RetryConfig()
    
    # Initialize caching if enabled
    if config.enable_cache:
        try:
            initialize_litellm_cache()
        except Exception as e:
            logger.warning(f"Failed to initialize cache: {e}")
    
    # Enable JSON schema validation if response format is provided
    if response_format:
        litellm.enable_json_schema_validation = True
    
    # Keep track of the conversation for retry context
    conversation_messages = list(messages)
    
    for attempt in range(config.max_attempts):
        try:
            if config.debug_mode:
                logger.debug(f"Attempt {attempt + 1}/{config.max_attempts}")
                logger.debug(f"Messages: {conversation_messages}")
            
            # Make the LLM call
            if response_format:
                response = await llm_call(
                    messages=conversation_messages,
                    response_format=response_format,
                    **kwargs
                )
            else:
                response = await llm_call(
                    messages=conversation_messages,
                    **kwargs
                )
            
            # Apply validation strategies
            all_valid = True
            validation_errors = []
            debug_info = {}
            
            for strategy in validation_strategies:
                context = {
                    "attempt": attempt,
                    "messages": conversation_messages,
                    "config": config,
                }
                
                # Validate the response
                result = await validate_response(strategy, response, context)
                
                if config.debug_mode:
                    logger.debug(f"{strategy.name}: {result}")
                    debug_info[strategy.name] = result
                
                if not result.valid:
                    all_valid = False
                    validation_errors.append(result)
            
            if all_valid:
                if config.debug_mode:
                    logger.debug(f"All validations passed on attempt {attempt + 1}")
                return response
            
            # If validation failed, add feedback to the conversation
            if attempt < config.max_attempts - 1:  # Not the last attempt
                # Add the failed response
                conversation_messages.append({
                    "role": "assistant",
                    "content": str(response)
                })
                
                # Create detailed feedback message
                feedback_parts = []
                for error in validation_errors:
                    feedback_parts.append(f"- {error.error}")
                    if error.suggestions:
                        feedback_parts.extend([f"  Suggestion: {s}" for s in error.suggestions])
                
                feedback_message = "Please fix these validation errors:\\n" + "\\n".join(feedback_parts)
                
                conversation_messages.append({
                    "role": "user",
                    "content": feedback_message
                })
                
                # Calculate and apply delay
                delay = config.calculate_delay(attempt)
                if config.debug_mode:
                    logger.debug(f"Waiting {delay} seconds before retry...")
                await asyncio.sleep(delay)
            
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed with error: {e}")
            if attempt == config.max_attempts - 1:
                raise
            
            # Calculate and apply delay for error retry
            delay = config.calculate_delay(attempt)
            await asyncio.sleep(delay)
    
    # If we get here, all attempts failed
    raise Exception(
        f"Failed after {config.max_attempts} attempts. "
        f"Last validation errors: {[e.error for e in validation_errors]}"
    )


def retry_with_validation_sync(
    llm_call: Callable,
    messages: List[Dict[str, str]],
    response_format: Optional[BaseModel],
    validation_strategies: List[ValidationStrategy],
    config: RetryConfig = None,
    **kwargs
) -> Any:
    """Synchronous version of retry_with_validation.
    
    Args:
        llm_call: The LLM completion function to call
        messages: List of messages for the conversation
        response_format: Optional Pydantic model for structured outputs
        validation_strategies: List of validation strategies to apply  
        config: Retry configuration
        **kwargs: Additional arguments passed to llm_call
    
    Returns:
        The validated LLM response
    """
    if config is None:
        config = RetryConfig()
    
    # Initialize caching if enabled
    if config.enable_cache:
        try:
            initialize_litellm_cache()
        except Exception as e:
            logger.warning(f"Failed to initialize cache: {e}")
    
    # Enable JSON schema validation if response format is provided
    if response_format:
        litellm.enable_json_schema_validation = True
    
    conversation_messages = list(messages)
    
    for attempt in range(config.max_attempts):
        try:
            if config.debug_mode:
                logger.debug(f"Attempt {attempt + 1}/{config.max_attempts}")
            
            # Make the LLM call
            if response_format:
                response = llm_call(
                    messages=conversation_messages,
                    response_format=response_format,
                    **kwargs
                )
            else:
                response = llm_call(
                    messages=conversation_messages,
                    **kwargs
                )
            
            # Apply validation strategies
            all_valid = True
            validation_errors = []
            
            for strategy in validation_strategies:
                context = {
                    "attempt": attempt,
                    "messages": conversation_messages,
                    "config": config,
                }
                
                result = strategy.validate(response, context)
                
                if config.debug_mode:
                    logger.debug(f"{strategy.name}: {result}")
                
                if not result.valid:
                    all_valid = False
                    validation_errors.append(result)
            
            if all_valid:
                return response
            
            # Add feedback for retry
            if attempt < config.max_attempts - 1:
                conversation_messages.append({
                    "role": "assistant",
                    "content": str(response)
                })
                
                feedback_parts = []
                for error in validation_errors:
                    feedback_parts.append(f"- {error.error}")
                    if error.suggestions:
                        feedback_parts.extend([f"  Suggestion: {s}" for s in error.suggestions])
                
                feedback_message = "Please fix these validation errors:\\n" + "\\n".join(feedback_parts)
                conversation_messages.append({
                    "role": "user",
                    "content": feedback_message
                })
                
                delay = config.calculate_delay(attempt)
                time.sleep(delay)
                
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt == config.max_attempts - 1:
                raise
            
            delay = config.calculate_delay(attempt)
            time.sleep(delay)
    
    raise Exception(f"Failed after {config.max_attempts} attempts")


async def validate_response(
    strategy: ValidationStrategy,
    response: Any,
    context: Dict[str, Any]
) -> ValidationResult:
    """Validate a response using the given strategy.
    
    Handles both sync and async validation strategies.
    """
    if hasattr(strategy, '__avalidate__') or asyncio.iscoroutinefunction(strategy.validate):
        return await strategy.validate(response, context)
    else:
        # Run sync validation in executor to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, strategy.validate, response, context)