"""
MARKER FORK ADDITION - LiteLLM Integration

Module: litellm.py
Description: LiteLLM service for unified LLM access across multiple providers

External Dependencies:
- litellm: https://docs.litellm.ai/
- PIL: Python Imaging Library
- pydantic: https://docs.pydantic.dev/
- tenacity: https://tenacity.readthedocs.io/

Example Usage:
>>> from extractor.core.services.litellm import LiteLLMService
>>> service = LiteLLMService({"litellm_model": "moonshot/kimi-k2-turbo-preview"})
>>> result = service(prompt, image, block, ResponseSchema)
"""

from __future__ import annotations

import base64
import json
import os
import time
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Annotated

import litellm
import PIL
from PIL import Image
from pydantic import BaseModel
from loguru import logger
from dotenv import find_dotenv, load_dotenv
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)

from extractor.core.schema.blocks import Block
from extractor.core.services import BaseService
from extractor.core.services.utils.log_utils import (
    log_api_request,
    log_api_response,
    log_api_error,
)
from extractor.core.services.utils.json_utils import clean_json_string
from extractor.core.services.utils.litellm_cache import initialize_litellm_cache
from litellm import completion_cost

# --------------------------------------------------------------------------- #
# Environment
# --------------------------------------------------------------------------- #
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)
project_root = Path(dotenv_path).parent

# --------------------------------------------------------------------------- #
# Tenacity retry decorator
# --------------------------------------------------------------------------- #
@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
    retry=retry_if_exception_type((
        litellm.exceptions.Timeout,
        litellm.exceptions.RateLimitError,
    )),
)
def _call_litellm(**kwargs):
    """Internal wrapper around litellm.completion with Tenacity retries."""
    return litellm.completion(**kwargs)

# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #
class LiteLLMService(BaseService):
    litellm_model: Annotated[
        str,
        "The model name to use for LiteLLM in provider/model format "
        "(e.g. 'openai/gpt-4o-mini', 'moonshot/kimi-k2-0711-preview').",
    ] = "moonshot/kimi-k2-0711-preview"

    litellm_api_key: Annotated[
        Optional[str],
        "The API key to use. If not provided, will use environment variables "
        "based on the provider.",
    ] = None

    litellm_base_url: Annotated[
        Optional[str], "Optional base URL for the API (for custom endpoints)."
    ] = None

    enable_cache: Annotated[bool, "Whether to enable caching for LLM responses."] = True

    # --------------------------------------------------------------------- #
    # Initialisation
    # --------------------------------------------------------------------- #
    def __init__(self, config: Optional[BaseModel | dict] = None) -> None:
        super().__init__(config)

        # LiteLLM global tweaks
        litellm.enable_json_schema_validation = True

        # Cache init
        if self.enable_cache:
            try:
                initialize_litellm_cache()
                logger.info("LiteLLM cache initialised")
            except Exception as exc:
                logger.warning(f"Failed to initialise LiteLLM cache: {exc}")

    # --------------------------------------------------------------------- #
    # Helpers
    # --------------------------------------------------------------------- #
    @staticmethod
    def _image_to_base64(image: PIL.Image.Image) -> str:
        """Convert PIL image to base64 string."""
        buffer = BytesIO()
        image.save(buffer, format="WEBP")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def _prepare_images(self, images: List[PIL.Image.Image]) -> List[dict]:
        """Prepare images for LiteLLM format."""
        return [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/webp;base64,{self._image_to_base64(img)}"},
            }
            for img in images
        ]

    # --------------------------------------------------------------------- #
    # Core API
    # --------------------------------------------------------------------- #
    def __call__(
        self,
        prompt: str,
        image: PIL.Image.Image | List[PIL.Image.Image],
        block: Block,
        response_schema: type[BaseModel],
        max_retries: int | None = None,
        timeout: int | None = None,
    ) -> dict:
        max_retries = max_retries if max_retries is not None else self.max_retries
        timeout = timeout if timeout is not None else self.timeout

        # Normalise images
        images = image if isinstance(image, list) else [image]

        # Build messages
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant that always responds "
                "with valid JSON matching the provided schema.",
            },
            {
                "role": "user",
                "content": [*self._prepare_images(images), {"type": "text", "text": prompt}],
            },
        ]

        # Build kwargs for litellm.completion
        litellm_kwargs = {
            "model": self.litellm_model,
            "messages": messages,
            "temperature": 0,
            "timeout": timeout,
        }

        # Optional overrides
        if self.litellm_base_url:
            litellm_kwargs["api_base"] = self.litellm_base_url
        if self.litellm_api_key:
            litellm_kwargs["api_key"] = self.litellm_api_key
        if self.litellm_model.startswith(("openai/", "azure/")):
            litellm_kwargs["response_format"] = {"type": "json_object"}

        # ------------------------------------------------------------------ #
        # Perform call with Tenacity retries
        # ------------------------------------------------------------------ #
        try:
            log_api_request("LiteLLM", litellm_kwargs)
            response = _call_litellm(**litellm_kwargs)
            log_api_response("LiteLLM", response)

            # Extract textual answer
            text = response.choices[0].message.content
            tokens = response.usage.total_tokens if response.usage else 0

            # Monetary cost (USD)
            cost_usd = float(completion_cost(completion_response=response))

            # Update block metadata
            metadata_update = {
                'llm_tokens_used': tokens,
                'llm_request_count': 1
            }
            
            # Store cost in result instead of metadata
            # since BlockMetadata doesn't have llm_cost_usd field
            block.update_metadata(**metadata_update)

            # Return parsed JSON with cost
            result = clean_json_string(text, return_dict=True)
            result['completion_cost'] = cost_usd
            logger.info(f"LiteLLM completion cost: ${cost_usd:.6f}")
            return result

        except Exception as exc:
            log_api_error("LiteLLM", exc, litellm_kwargs)
            logger.error(f"LiteLLM call failed after retries: {exc}")
            return {}