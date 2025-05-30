"""LiteLLM integration with validation loop support."""

import os
from typing import Any, Dict, List, Optional, Union

import litellm
from PIL import Image
from pydantic import BaseModel

from marker.core.llm_call.core import retry_with_validation, RetryConfig
from marker.core.llm_call.core.base import ValidationStrategy
from marker.core.llm_call.core.strategies import registry
from marker.core.llm_call.service import ValidatedLiteLLMService
from marker.core.schema.blocks import Block
from marker.core.services.litellm import LiteLLMService
from marker.core.services.utils.litellm_cache import initialize_litellm_cache


def completion_with_validation(
    model: str,
    messages: List[Dict[str, str]],
    response_format: Optional[type[BaseModel]] = None,
    validation_strategies: Optional[List[Union[str, ValidationStrategy]]] = None,
    max_retries: int = 3,
    enable_cache: bool = True,
    debug: bool = False,
) -> Any:
    """
    Enhanced completion function with validation loop support.
    
    This function provides the same interface as litellm.completion but adds
    validation and retry capabilities.
    
    Args:
        model: The model to use (e.g., "gemini/gemini-1.5-pro")
        messages: The messages to send to the model
        response_format: Optional Pydantic model for response validation
        validation_strategies: List of validation strategies to apply
        max_retries: Maximum number of retry attempts
        enable_cache: Whether to enable Redis caching
        debug: Enable debug mode for detailed logging
        
    Returns:
        The validated response from the model
    """
    # Initialize cache if enabled
    if enable_cache:
        try:
            initialize_litellm_cache()
        except Exception as e:
            print(f"Failed to initialize cache: {e}")
            print("Continuing without cache")
    
    # Enable JSON schema validation if response format is provided
    if response_format:
        litellm.enable_json_schema_validation = True
    
    # Convert string strategies to actual strategy objects
    strategies = []
    if validation_strategies:
        for strategy in validation_strategies:
            if isinstance(strategy, str):
                # Parse strategy string
                if "(" in strategy:
                    name, params_str = strategy.split("(", 1)
                    params_str = params_str.rstrip(")")
                    # Parse parameters
                    params = {}
                    if params_str:
                        for param in params_str.split(","):
                            key, value = param.split("=")
                            params[key.strip()] = eval(value.strip())
                    strategy_obj = registry.get(name, **params)
                else:
                    strategy_obj = registry.get(strategy)
                strategies.append(strategy_obj)
            else:
                strategies.append(strategy)
    
    # Create retry configuration
    config = RetryConfig(
        max_attempts=max_retries,
        debug_mode=debug
    )
    
    # Use the validation-aware retry mechanism
    if strategies:
        return retry_with_validation(
            llm_call=lambda messages, response_format: litellm.completion(
                model=model,
                messages=messages,
                response_format=response_format
            ),
            messages=messages,
            response_format=response_format,
            validation_strategies=strategies,
            config=config
        )
    else:
        # No validation strategies, just use litellm directly
        return litellm.completion(
            model=model,
            messages=messages,
            response_format=response_format
        )


def create_validated_litellm_service(config: Optional[Dict[str, Any]] = None) -> ValidatedLiteLLMService:
    """
    Create a ValidatedLiteLLMService with default configuration.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        A configured ValidatedLiteLLMService instance
    """
    default_config = {
        "enable_validation_loop": os.getenv("ENABLE_LLM_VALIDATION", "false").lower() == "true",
        "default_model": os.getenv("LITELLM_DEFAULT_MODEL", "vertex_ai/gemini-2.5-flash-preview-04-17"),
        "judge_model": os.getenv("LITELLM_JUDGE_MODEL", "vertex_ai/gemini-2.5-flash-preview-04-17"),
        "enable_cache": True,
    }
    
    if config:
        default_config.update(config)
    
    return ValidatedLiteLLMService(default_config)


# Example usage following the user's provided pattern
if __name__ == "__main__":
    import litellm
    from litellm import completion
    from pydantic import BaseModel
    
    # Initialize Redis caching
    initialize_litellm_cache()
    
    messages = [
        {"role": "system", "content": "Extract the event information."},
        {"role": "user", "content": "Alice and Bob are going to a science fair on Friday."},
    ]
    
    litellm.enable_json_schema_validation = True
    
    class CalendarEvent(BaseModel):
        name: str
        date: str
        participants: list[str]
    
    # First call - will miss cache
    resp = completion(
        model="gemini/gemini-1.5-pro",
        messages=messages,
        response_format=CalendarEvent,
    )
    
    print("Received={}".format(resp))
    
    # Second call - should hit cache
    resp2 = completion(
        model="gemini/gemini-1.5-pro",
        messages=messages,
        response_format=CalendarEvent,
    )
    
    # Check if it was a cache hit
    cache_hit = getattr(resp2, "_hidden_params", {}).get("cache_hit")
    print(f"Second call cache hit: {cache_hit}")
    
    # Example with validation
    resp3 = completion_with_validation(
        model="gemini/gemini-1.5-pro",
        messages=messages,
        response_format=CalendarEvent,
        validation_strategies=[
            "field_presence(required_fields=['name', 'date', 'participants'])",
            "length_check(field_name='name', min_length=1)"
        ],
        max_retries=3,
        enable_cache=True
    )