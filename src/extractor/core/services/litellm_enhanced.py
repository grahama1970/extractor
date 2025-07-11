"""
Module: litellm_enhanced.py
Description: Enhanced LiteLLM service with optional validation loop support
"""

import os
from typing import Any, List, Optional, Union

import litellm
from PIL import Image
from pydantic import BaseModel, Field

from extractor.core.schema.blocks import Block
from extractor.core.services.litellm import LiteLLMService
from extractor.core.llm_call.core import retry_with_validation, retry_with_validation_sync, RetryConfig
from extractor.core.llm_call.core.strategies import registry


class EnhancedLiteLLMService(LiteLLMService):
    """
    Enhanced LiteLLM service that adds optional validation loop support
    while maintaining full backward compatibility with the existing service.
    """
    
    # Validation configuration
    enable_validation_loop: bool = Field(
        default=False,
        description="Enable validation loop for LLM responses"
    )
    validation_strategies: List[str] = Field(
        default_factory=list,
        description="List of validation strategies to apply"
    )
    json_schema_validation: bool = Field(
        default=True,
        description="Enable LiteLLM's JSON schema validation"
    )
    max_validation_retries: int = Field(
        default=3,
        description="Maximum retries for validation failures"
    )
    
    def __init__(self, config: Optional[BaseModel | dict] = None):
        """Initialize the enhanced service."""
        super().__init__(config)
        
        # Load validation settings from environment if not provided
        if not self.enable_validation_loop:
            self.enable_validation_loop = os.getenv("ENABLE_LLM_VALIDATION", "false").lower() == "true"
        
        # Set up JSON schema validation
        if self.json_schema_validation:
            litellm.enable_json_schema_validation = True
    
    def _get_validation_strategies(self):
        """Convert string strategy names to actual strategy objects."""
        strategies = []
        for strategy_spec in self.validation_strategies:
            try:
                if "(" in strategy_spec:
                    # Parse strategy with parameters
                    name, params_str = strategy_spec.split("(", 1)
                    params_str = params_str.rstrip(")")
                    params = {}
                    if params_str:
                        for param in params_str.split(","):
                            key, value = param.split("=")
                            params[key.strip()] = eval(value.strip())
                    strategy = registry.get(name, **params)
                else:
                    strategy = registry.get(strategy_spec)
                strategies.append(strategy)
            except Exception as e:
                print(f"Warning: Could not load strategy '{strategy_spec}': {e}")
        return strategies
    
    def __call__(
        self,
        prompt: str,
        image: Union[Image.Image, List[Image.Image]],
        block: Block,
        response_schema: type[BaseModel],
        max_retries: int | None = None,
        timeout: int | None = None,
    ):
        """
        Enhanced call method that optionally uses validation loop.
        
        If validation is enabled, uses the retry mechanism with validation strategies.
        Otherwise, falls back to the standard LiteLLM behavior.
        """
        if not self.enable_validation_loop:
            # Use standard behavior when validation is disabled
            return super().__call__(prompt, image, block, response_schema, max_retries, timeout)
        
        # Validation-enabled path
        if max_retries is None:
            max_retries = self.max_validation_retries
        
        if timeout is None:
            timeout = self.timeout
        
        if not isinstance(image, list):
            image = [image]
        
        image_data = self.prepare_images(image)
        
        # Prepare messages
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant that always responds with valid JSON. Your response must be compatible with the provided schema."
            },
            {
                "role": "user",
                "content": [
                    *image_data,
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        
        # Get API key
        api_key = self.get_api_key(self.litellm_model)
        if not api_key:
            raise ValueError(f"No API key found for model {self.litellm_model}")
        
        # Create LLM call function
        def llm_call(messages, response_format):
            litellm_config = {
                "api_key": api_key,
                "timeout": timeout,
            }
            
            if self.litellm_base_url and self.litellm_base_url.strip():
                litellm_config["api_base"] = self.litellm_base_url
            
            headers = {
                "X-Title": "Marker",
                "HTTP-Referer": "https://github.com/VikParuchuri/marker",
            }
            
            litellm_kwargs = {
                "model": self.litellm_model,
                "messages": messages,
                **litellm_config,
                "extra_headers": headers
            }
            
            # Add response_format for OpenAI models
            if self.litellm_model.startswith("openai/") or self.litellm_model.startswith("azure/"):
                litellm_kwargs["response_format"] = {"type": "json_object"}
            
            # Add JSON instruction for Vertex AI/Gemini models
            if self.litellm_model.startswith("vertex") or self.litellm_model.startswith("gemini"):
                if messages[0]["role"] == "system":
                    messages[0]["content"] += " Always respond with valid JSON format."
            
            response = litellm.completion(**litellm_kwargs)
            
            # Extract and parse response
            response_text = response.choices[0].message.content
            total_tokens = response.usage.total_tokens
            
            # Update block metadata
            block.update_metadata(llm_tokens_used=total_tokens, llm_request_count=1)
            
            # Return parsed JSON
            from extractor.core.services.utils.json_utils import clean_json_string
            return clean_json_string(response_text, return_dict=True)
        
        # Get validation strategies
        strategies = self._get_validation_strategies()
        
        # Create retry configuration
        config = RetryConfig(
            max_attempts=max_retries,
            debug_mode=False  # Set to True for debugging
        )
        
        # Use validation-aware retry mechanism
        try:
            # Use sync version for compatibility
            result = retry_with_validation_sync(
                llm_call=llm_call,
                messages=messages,
                response_format=response_schema,
                validation_strategies=strategies,
                config=config
            )
            return result
        except Exception as e:
            print(f"Validation-enhanced call failed: {e}")
            # Fallback to standard behavior on error
            return super().__call__(prompt, image, block, response_schema, max_retries, timeout)


# Factory function to create enhanced service
def create_enhanced_litellm_service(config: Optional[dict] = None) -> EnhancedLiteLLMService:
    """
    Create an enhanced LiteLLM service with validation capabilities.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Configured EnhancedLiteLLMService instance
    """
    default_config = {
        "enable_validation_loop": os.getenv("ENABLE_LLM_VALIDATION", "false").lower() == "true",
        "litellm_model": os.getenv("LITELLM_DEFAULT_MODEL", "vertex_ai/gemini-2.5-flash-preview-04-17"),
        "validation_strategies": os.getenv("LITELLM_VALIDATION_STRATEGIES", "").split(",") if os.getenv("LITELLM_VALIDATION_STRATEGIES") else [],
        "enable_cache": True,
    }
    
    if config:
        default_config.update(config)
    
    return EnhancedLiteLLMService(default_config)