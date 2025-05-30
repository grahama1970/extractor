import base64
import json
import os
import time
from io import BytesIO
from typing import Annotated, List, Union, Optional

import litellm
import PIL
from PIL import Image
from pydantic import BaseModel

from marker.core.schema.blocks import Block
from marker.core.services import BaseService
from marker.core.services.utils.log_utils import log_api_request, log_api_response, log_api_error
from marker.core.services.utils.json_utils import clean_json_string

# Import cache initialization from the utils directory
try:
    from marker.core.services.utils.litellm_cache import initialize_litellm_cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False


class LiteLLMService(BaseService):
    # Note: This is not a required field as it will be loaded from env vars if not provided
    litellm_api_key: Annotated[
        str,
        "The API key to use for the LiteLLM service. If not provided, will attempt to use the appropriate environment variable based on the model provider."
    ] = ""
    litellm_model: Annotated[
        str,
        "The model name to use for LiteLLM in provider/model format (e.g. 'openai/gpt-4o-mini', 'vertex/gemini-pro-vision')."
    ] = "vertex_ai/gemini-2.0-flash"
    litellm_base_url: Annotated[
        Optional[str],
        "Optional base URL for the API (for custom endpoints)."
    ] = ""
    enable_cache: Annotated[
        bool,
        "Whether to enable caching for LLM responses. This can reduce API costs and improve performance."
    ] = True

    def __init__(self, config: Optional[BaseModel | dict] = None):
        super().__init__(config)

        # Initialize cache if available and enabled
        if self.enable_cache and CACHE_AVAILABLE:
            try:
                initialize_litellm_cache()
                print("LiteLLM cache initialized")
            except Exception as e:
                print(f"Failed to initialize LiteLLM cache: {e}")
                print("Continuing without cache")
        elif self.enable_cache:
            print("LiteLLM cache not available (marker/services/utils/litellm_cache.py not found)")
            print("Continuing without cache")

    def get_api_key(self, model: str):
        """
        Get the appropriate API key based on the model provider.
        If no API key is provided directly, it will look for the appropriate
        environment variable based on the provider prefix in the model name.

        Args:
            model: The model name in provider/model format

        Returns:
            str: The API key to use
        """
        # If API key is directly provided (not empty), use it
        if self.litellm_api_key and self.litellm_api_key.strip():
            return self.litellm_api_key

        # Otherwise, try to get the API key from environment variables
        # based on the provider prefix
        if "/" not in model:
            # Default to OpenAI if no provider is specified
            return os.environ.get("OPENAI_API_KEY")

        provider = model.split("/")[0].lower()

        # Map provider to environment variable
        provider_to_env = {
            "openai": "OPENAI_API_KEY",
            "azure": "AZURE_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "claude": "ANTHROPIC_API_KEY",
            "vertex": "VERTEX_PROJECT",
            "vertex_ai": "VERTEX_PROJECT",
            "google": "GOOGLE_API_KEY",
            "gemini": "GOOGLE_API_KEY",
            "ollama": "OLLAMA_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "cohere": "COHERE_API_KEY",
            "groq": "GROQ_API_KEY",
        }

        env_var = provider_to_env.get(provider, "OPENAI_API_KEY")
        api_key = os.environ.get(env_var)

        # Log which environment variable we're using (without showing the actual key)
        print(f"Using API key from environment variable: {env_var}")

        return api_key

    def image_to_base64(self, image: PIL.Image.Image):
        image_bytes = BytesIO()
        image.save(image_bytes, format="WEBP")
        return base64.b64encode(image_bytes.getvalue()).decode("utf-8")

    def prepare_images(
        self, images: Union[Image.Image, List[Image.Image]]
    ) -> List[dict]:
        if isinstance(images, Image.Image):
            images = [images]

        return [
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/webp;base64,{}".format(
                        self.image_to_base64(img)
                    ),
                }
            }
            for img in images
        ]

    def __call__(
        self,
        prompt: str,
        image: PIL.Image.Image | List[PIL.Image.Image],
        block: Block,
        response_schema: type[BaseModel],
        max_retries: int | None = None,
        timeout: int | None = None,
    ):
        if max_retries is None:
            max_retries = self.max_retries

        if timeout is None:
            timeout = self.timeout

        if not isinstance(image, list):
            image = [image]

        image_data = self.prepare_images(image)

        # Add system message to ensure JSON output
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

        # Parse model provider and name from litellm_model
        model = self.litellm_model

        # Get the appropriate API key based on the model provider
        api_key = self.get_api_key(model)
        if not api_key:
            raise ValueError(f"No API key found for model {model}. Please provide an API key directly or set the appropriate environment variable.")

        # Configure litellm
        litellm_config = {
            "api_key": api_key,
            "timeout": timeout,
        }

        # Add base_url if provided and not empty
        if self.litellm_base_url and self.litellm_base_url.strip():
            litellm_config["api_base"] = self.litellm_base_url

        tries = 0
        while tries < max_retries:
            try:
                # Set custom headers
                headers = {
                    "X-Title": "Marker",
                    "HTTP-Referer": "https://github.com/VikParuchuri/marker",
                }

                # Make the API call through litellm
                # Handle response format based on model provider
                litellm_kwargs = {
                    "model": model,
                    "messages": messages,
                    **litellm_config,
                    "extra_headers": headers
                }

                # Add response_format if it's an OpenAI model (only format they support)
                if model.startswith("openai/") or model.startswith("azure/"):
                    litellm_kwargs["response_format"] = {"type": "json_object"}
                
                # For Vertex AI/Gemini models, add JSON instruction to the prompt
                if model.startswith("vertex") or model.startswith("gemini"):
                    if messages[0]["role"] == "system":
                        messages[0]["content"] += " Always respond with valid JSON format."
                    else:
                        messages.insert(0, {
                            "role": "system", 
                            "content": "Always respond with valid JSON format."
                        })

                # Log the API request
                log_api_request("LiteLLM", litellm_kwargs)

                # Make the API call through litellm
                response = litellm.completion(**litellm_kwargs)

                # Log the API response
                log_api_response("LiteLLM", response)

                response_text = response.choices[0].message.content
                total_tokens = response.usage.total_tokens
                block.update_metadata(llm_tokens_used=total_tokens, llm_request_count=1)

                # Use clean_json_string instead of json.loads
                return clean_json_string(response_text, return_dict=True)
            except litellm.exceptions.Timeout as e:
                # Timeout error
                tries += 1
                wait_time = tries * 3
                log_api_error("LiteLLM", e, litellm_kwargs)
                print(
                    f"Timeout error: {e}. Retrying in {wait_time} seconds... (Attempt {tries}/{max_retries})"
                )
                time.sleep(wait_time)
            except litellm.exceptions.RateLimitError as e:
                # Rate limit exceeded
                tries += 1
                wait_time = tries * 3
                log_api_error("LiteLLM", e, litellm_kwargs)
                print(
                    f"Rate limit error: {e}. Retrying in {wait_time} seconds... (Attempt {tries}/{max_retries})"
                )
                time.sleep(wait_time)
            except Exception as e:
                log_api_error("LiteLLM", e, litellm_kwargs)
                print(f"Error in LiteLLM service: {e}")
                break

        return {}