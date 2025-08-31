"""
Module: litellm_call.py
Description: Large Language Model integration and management

External Dependencies:
- litellm: https://docs.litellm.ai/
- pydantic: https://docs.pydantic.dev/
- loguru: https://loguru.readthedocs.io/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

from types import SimpleNamespace
import litellm
import async_timeout
from deepmerge import always_merger
from pydantic import BaseModel, Field
import asyncio
import os
import copy
from typing import Any, AsyncGenerator, Dict, Type, Union
from pydantic import BaseModel
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.generate_schema_for_llm.shared.multimodal_utils import format_multimodal_messages, is_multimodal
from src.utils.get_project_root import get_project_root, load_env_file
from src.utils.json_utils import clean_json_string

# Redis Caching of LiteLLM Call
async def initialize_litellm_cache():
    litellm.cache = litellm.Cache(
        type="redis",
        host="localhost",  # Redis is accessible on localhost
        port=6379,         # Default Redis port
        password=None      # No password unless you configured one
    )
    litellm.enable_cache()
    os.environ['LITELLM_LOG'] = 'DEBUG'


# Load environment variables Globally
project_dir = get_project_root()
load_env_file(env_type="backend")




# Helper function to validate and update LLM config
def validate_update_config(config: Dict[str, Any], insert_into_db: bool = False) -> Dict[str, Any]:
    """
    Validates and updates LLM config to meet requirements for JSON/structured responses.
    
    Args:
        llm_config: The LLM configuration dictionary
        
    Returns:
        Dict[str, Any]: Updated LLM config with proper JSON formatting instructions
        
    Raises:
        ValueError: If JSON requirements cannot be met
    """
    llm_config = config.get("llm_config", {})
    directories = config.get("directories", {})
    if not llm_config.get("messages", []):
        raise ValueError("A message object is required to query the LLM")
        
    
    response_format = llm_config.get("response_format")
    requires_json = response_format == "json" or (
        isinstance(response_format, type) and 
        issubclass(response_format, BaseModel)
    )
    
    if requires_json:
        messages = llm_config.get("messages", []).copy()
        system_messages = [msg for msg in messages if msg.get("role") == "system"]
        
        if not system_messages:
            # Add a new system message if none exists
            messages.insert(0, {
                "role": "system",
                "content": "You must return your response as a well-formatted JSON object."
            })
        else:
            # Update existing system message if JSON instruction is missing
            system_content = system_messages[0].get("content", "").lower()
            json_instruction_keywords = ["json", "well-formatted", "well formatted"]
            
            if not any(keyword in system_content for keyword in json_instruction_keywords):
                system_messages[0]["content"] = (
                    "You must return your response as a well-formatted JSON object. "
                    + system_messages[0]["content"]
                )

        # Check for multimodal content
        if is_multimodal(messages):
            # hardcoded for now
            image_directory = directories.get("image_directory", "")
            max_size_kb = llm_config.get("max_image_size_kb", 500)
            messages = format_multimodal_messages(messages, image_directory, max_size_kb)
        
        llm_config = copy.deepcopy(llm_config)
        llm_config["messages"] = messages
        
    return llm_config


# Main
@retry(
    wait=wait_exponential(multiplier=1, min=4, max=10),  # Exponential backoff
    stop=stop_after_attempt(3),  # Max 3 retries
    retry=retry_if_exception_type(Exception),  # Retry on any exception
)
async def litellm_call(config: Dict) -> Union[BaseModel, Dict[str, Any], str]:
    try:
        llm_config = config.get("llm_config", {})
        directories = config.get("directories", {})

        llm_config = validate_update_config(config)
        
        # Default to plain text if response_format is not provided
        response_format = llm_config.get("response_format", None)
        
        api_params = {
            "model": llm_config.get("model", "openai/gpt-4o-mini"),
            "messages": llm_config.get("messages", []),
            "temperature": llm_config.get("temperature", .2),
            "max_tokens": llm_config.get("max_tokens", 1000),
            "stream": llm_config.get("stream", False),
            "caching": llm_config.get("caching", True),
            "metadata": {"request_id": llm_config.get("request_id"), "hidden": True},
        }
        if llm_config.get("api_base", None):
            
            # Remove /v1/completions from api_base if present
            # Strange LiteLLM behavior, but it works
            api_base = llm_config["api_base"]
            if api_base.endswith("/v1/completions"):
                api_base = api_base.replace("/v1/completions", "/v1")
                api_params["api_base"] = api_base

        # Add response_format only if explicitly provided
        if response_format:
            api_params["response_format"] = response_format

        response = await litellm.acompletion(**api_params)

        # Handle streaming response
        if llm_config.get("stream", False):
            full_content = ""
            async for chunk in response:
                content = chunk.choices[0].delta.content or ""
                full_content += content
            content = full_content

            # Construct a mock response object similar to non-streaming responses
            # Not sure if I need to use this...we'll see
            reconstructed_response = SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=full_content,
                            role="assistant"
                        )
                    )
                ],
                _hidden_params={
                    "cache_hit": False,
                    "request_id": llm_config.get("request_id"),
                    "hidden": True
                }
            )
            return reconstructed_response
        else:
            # Handle non-streaming response
            hidden_params = response._hidden_params
            logger.info(f"Cache Hit: {hidden_params.get('cache_hit', False)}")
            content = response.choices[0].message.content
        
        # should we insert the message object into the db with an embed here
        
        
        return response
    

    except litellm.BadRequestError as e:
        logger.error(f"BadRequestError: {e}")
        raise
    except Exception as e:
        logger.error(f"Error calling LLM: {e}")
        raise


# Usage
async def main():
    litellm.set_verbose=True
    await initialize_litellm_cache()
    from src.settings.config import config
    
    # Define a Pydantic model for the response
    class UserDetails(BaseModel):
        """A model representing user details including name, age and favorite color"""
        name: str = Field(description="The user's full name")
        # age: int = Field(ge=1, le=120, description="The user's age in years")
        age: int = Field(description="The user's age in years")
        favorite_color: str = Field(description="The user's preferred color")
    
    updates = {
        "llm_config": {
            # "api_base": "https://api.openai.com/v1",
            # "model": "openai/gpt-4o-mini",
            "api_base": "http://192.168.86.49:30002/v1/completions",
            "model": "openai/neuralmagic/Meta-Llama-3.1-8B-Instruct-FP8",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant. You must return your response as a well-formatted JSON object. with no other text."},
                {"role": "user", "content": "Tell me about John Doe, age 30 and his favorite color is blue, in JSON format."}
            ],
            "response_format": UserDetails, # {"type": "json_object"}, # UserDetails,
            "stream": True,
            "max_image_size_kb": 500, # for multimodal calls
            "caching": True,
        }
    }
    config = always_merger.merge(config, updates)


    response = await litellm_call(config)

    content = response.choices[0].message.content
    hidden_params = response._hidden_params
    print(content)
    print(hidden_params)

    

if __name__ == "__main__":
    asyncio.run(main())
    