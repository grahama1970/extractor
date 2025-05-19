"""Enhanced LiteLLM service with validation loop support.

This module provides a wrapper service that adds validation capabilities
to the existing LiteLLMService without modifying the original implementation.
"""

import os
from typing import Any, Dict, List, Optional, Union

import litellm
from pydantic import BaseModel

from marker.llm_call.core.base import ValidationStrategy
from marker.llm_call.core.retry import (
    RetryConfig,
    retry_with_validation,
    retry_with_validation_sync,
)
from marker.llm_call.core.strategies import registry
from marker.schema.blocks import Block
from marker.services.litellm import LiteLLMService


class ValidatedLiteLLMService(LiteLLMService):
    """Enhanced LiteLLM service with optional validation loop.
    
    This service extends the existing LiteLLMService to add validation
    capabilities while maintaining full backward compatibility.
    """
    
    # Validation-specific configuration
    enable_validation_loop: bool = False
    validation_strategies: List[str] = []
    validation_config: Dict[str, Any] = {}
    default_model: Optional[str] = None
    judge_model: Optional[str] = None
    
    def __init__(self, config: Optional[BaseModel | dict] = None):
        """Initialize the service with optional validation configuration."""
        super().__init__(config)
        
        # Load validation configuration from environment if not provided
        if self.default_model is None:
            self.default_model = os.getenv(
                "LITELLM_DEFAULT_MODEL", 
                "vertex_ai/gemini-2.5-flash-preview-04-17"
            )
        
        if self.judge_model is None:
            self.judge_model = os.getenv(
                "LITELLM_JUDGE_MODEL",
                self.default_model
            )
        
        # Override model if using defaults
        if self.default_model and not self.litellm_model:
            self.litellm_model = self.default_model
        
        # Check if validation should be enabled from environment
        if not self.enable_validation_loop:
            self.enable_validation_loop = os.getenv(
                "ENABLE_LLM_VALIDATION", "false"
            ).lower() == "true"
    
    def __call__(
        self,
        prompt: str,
        image: Any,
        block: Block,
        response_schema: type[BaseModel],
        max_retries: int | None = None,
        timeout: int | None = None,
    ):
        """Call the LLM with optional validation loop.
        
        If validation is disabled, this behaves exactly like the parent class.
        If validation is enabled, it uses the retry mechanism with validation strategies.
        """
        if not self.enable_validation_loop:
            # Use original behavior
            return super().__call__(
                prompt, image, block, response_schema, max_retries, timeout
            )
        
        # Use validation-enhanced behavior
        return self._call_with_validation(
            prompt, image, block, response_schema, max_retries, timeout
        )
    
    def _call_with_validation(
        self,
        prompt: str,
        image: Any,
        block: Block,
        response_schema: type[BaseModel],
        max_retries: int | None = None,
        timeout: int | None = None,
    ):
        """Internal method that implements validation-enhanced calling."""
        if max_retries is None:
            max_retries = self.max_retries
        
        if timeout is None:
            timeout = self.timeout
        
        # Prepare messages
        messages = self._prepare_messages(prompt, image)
        
        # Get validation strategies
        strategies = self._get_validation_strategies()
        
        # Configure retry behavior
        retry_config = RetryConfig(
            max_attempts=max_retries,
            debug_mode=self.validation_config.get("debug_mode", False),
            enable_cache=self.enable_cache,
        )
        
        # Define the LLM call function
        def llm_call_fn(messages, response_format=None):
            """Wrapper function for LiteLLM completion."""
            kwargs = {
                "model": self.litellm_model,
                "messages": messages,
                "timeout": timeout,
            }
            
            # Add API key
            api_key = self.get_api_key(self.litellm_model)
            if api_key:
                kwargs["api_key"] = api_key
            
            # Add base URL if provided
            if self.litellm_base_url:
                kwargs["api_base"] = self.litellm_base_url
            
            # Add response format for supported models
            if response_format and (
                self.litellm_model.startswith("openai/") or 
                self.litellm_model.startswith("azure/")
            ):
                kwargs["response_format"] = {"type": "json_object"}
            
            # Add custom headers
            kwargs["extra_headers"] = {
                "X-Title": "Marker",
                "HTTP-Referer": "https://github.com/VikParuchuri/marker",
            }
            
            # Make the call
            response = litellm.completion(**kwargs)
            
            # Update block metadata
            if hasattr(response, 'usage'):
                block.update_metadata(
                    llm_tokens_used=response.usage.total_tokens,
                    llm_request_count=1
                )
            
            # Extract and parse response
            response_text = response.choices[0].message.content
            
            # Return parsed response
            from marker.services.utils.json_utils import clean_json_string
            return clean_json_string(response_text, return_dict=True)
        
        # Use the synchronous retry mechanism
        result = retry_with_validation_sync(
            llm_call=llm_call_fn,
            messages=messages,
            response_format=response_schema,
            validation_strategies=strategies,
            config=retry_config,
        )
        
        return result
    
    def _prepare_messages(self, prompt: str, image: Any) -> List[Dict[str, Any]]:
        """Prepare messages for LLM call."""
        if not isinstance(image, list):
            image = [image]
        
        image_data = self.prepare_images(image)
        
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant that always responds with valid JSON. Your response must be compatible with the provided schema and contain the word 'json' to ensure proper formatting."
            },
            {
                "role": "user",
                "content": [
                    *image_data,
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        
        # Add JSON instruction for Vertex AI models
        if self.litellm_model.startswith("vertex"):
            messages[0]["content"] += " Always respond with valid JSON format."
        
        return messages
    
    def _get_validation_strategies(self) -> List[ValidationStrategy]:
        """Get configured validation strategies."""
        strategies = []
        
        for strategy_name in self.validation_strategies:
            try:
                # Parse strategy name and config
                if "(" in strategy_name:
                    # Strategy with parameters
                    name, params_str = strategy_name.split("(", 1)
                    params_str = params_str.rstrip(")")
                    
                    # Parse parameters (simple key=value pairs)
                    params = {}
                    for param in params_str.split(","):
                        if "=" in param:
                            key, value = param.split("=", 1)
                            params[key.strip()] = value.strip()
                    
                    strategy = registry.get(name, **params)
                else:
                    # Strategy without parameters
                    strategy = registry.get(strategy_name)
                
                strategies.append(strategy)
                
            except Exception as e:
                print(f"Warning: Failed to load strategy '{strategy_name}': {e}")
        
        return strategies
    
    async def acall(
        self,
        prompt: str,
        image: Any,
        block: Block,
        response_schema: type[BaseModel],
        max_retries: int | None = None,
        timeout: int | None = None,
    ):
        """Async version of the call method with validation support."""
        if not self.enable_validation_loop:
            # For now, fall back to sync version as parent doesn't have async
            return self.__call__(
                prompt, image, block, response_schema, max_retries, timeout
            )
        
        # Use async validation
        if max_retries is None:
            max_retries = self.max_retries
        
        if timeout is None:
            timeout = self.timeout
        
        messages = self._prepare_messages(prompt, image)
        strategies = self._get_validation_strategies()
        
        retry_config = RetryConfig(
            max_attempts=max_retries,
            debug_mode=self.validation_config.get("debug_mode", False),
            enable_cache=self.enable_cache,
        )
        
        # Define async LLM call function
        async def async_llm_call(messages, response_format=None):
            """Async wrapper for LiteLLM completion."""
            kwargs = {
                "model": self.litellm_model,
                "messages": messages,
                "timeout": timeout,
            }
            
            api_key = self.get_api_key(self.litellm_model)
            if api_key:
                kwargs["api_key"] = api_key
            
            if self.litellm_base_url:
                kwargs["api_base"] = self.litellm_base_url
            
            if response_format and (
                self.litellm_model.startswith("openai/") or 
                self.litellm_model.startswith("azure/")
            ):
                kwargs["response_format"] = {"type": "json_object"}
            
            kwargs["extra_headers"] = {
                "X-Title": "Marker",
                "HTTP-Referer": "https://github.com/VikParuchuri/marker",
            }
            
            # Use async completion if available
            if hasattr(litellm, 'acompletion'):
                response = await litellm.acompletion(**kwargs)
            else:
                # Fall back to sync in executor
                import asyncio
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, litellm.completion, **kwargs
                )
            
            if hasattr(response, 'usage'):
                block.update_metadata(
                    llm_tokens_used=response.usage.total_tokens,
                    llm_request_count=1
                )
            
            response_text = response.choices[0].message.content
            
            from marker.services.utils.json_utils import clean_json_string
            return clean_json_string(response_text, return_dict=True)
        
        # Use async retry mechanism
        result = await retry_with_validation(
            llm_call=async_llm_call,
            messages=messages,
            response_format=response_schema,
            validation_strategies=strategies,
            config=retry_config,
        )
        
        return result