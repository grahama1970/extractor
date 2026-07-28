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
from io import BytesIO
import os
from pathlib import Path
from typing import List, Optional, Annotated

import json
import urllib.request
import urllib.error
import PIL
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
    retry=retry_if_exception_type((TimeoutError, urllib.error.HTTPError, urllib.error.URLError)),
)
def _openai_chat_request(
    api_base: str, api_key: str, payload: dict, timeout: int | None = None
) -> dict:
    base = api_base.rstrip("/")
    url = f"{base}/chat/completions"
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url=url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout or 30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
            return json.loads(body)
        except Exception:
            raise


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
        # Keep cache init a no-op for scillm/openai-http; log and continue
        try:
            if self.enable_cache:
                initialize_litellm_cache()
        except Exception:
            pass

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

        # Prepare OpenAI-compatible /v1/chat/completions payload (scillm backend)
        api_base = (
            self.litellm_base_url
            or os.getenv("OPENAI_BASE_URL")
            or os.getenv("OPENAI_API_BASE")
            or os.getenv("SCILLM_API_BASE", "http://localhost:4001")
            or ""
        ).rstrip("/")
        api_key = (
            self.litellm_api_key or os.getenv("OPENAI_API_KEY") or os.getenv("SCILLM_PROXY_KEY", "sk-dev-proxy-123") or ""
        )
        if not api_base or not api_key:
            logger.error(
                "Missing OPENAI_BASE_URL/OPENAI_API_BASE and/or OPENAI_API_KEY for scillm client."
            )
            return {}

        payload = {
            "model": (
                self.litellm_model
                if not self.litellm_model.startswith("openai/")
                else self.litellm_model.split("/", 1)[1]
            ),
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }

        # ------------------------------------------------------------------ #
        # Perform call with Tenacity retries
        # ------------------------------------------------------------------ #
        try:
            log_api_request("scillm-openai", {k: v for k, v in payload.items() if k != "messages"})
            response = _openai_chat_request(api_base + "/v1", api_key, payload, timeout)
            log_api_response("scillm-openai", response)

            # Extract textual answer
            text = ""
            try:
                text = (response.get("choices") or [{}])[0].get("message", {}).get("content", "")
            except Exception:
                text = ""
            tokens = int(((response.get("usage") or {}).get("total_tokens") or 0))

            # Monetary cost unknown via direct gateway → set to 0.0 for now
            cost_usd = 0.0

            # Update block metadata
            metadata_update = {"llm_tokens_used": tokens, "llm_request_count": 1}

            # Store cost in result instead of metadata
            # since BlockMetadata doesn't have llm_cost_usd field
            block.update_metadata(**metadata_update)

            # Return parsed JSON with cost
            result = clean_json_string(text, return_dict=True)
            result["completion_cost"] = cost_usd
            logger.info(f"LiteLLM completion cost: ${cost_usd:.6f}")
            return result

        except Exception as exc:
            log_api_error(
                "scillm-openai", exc, {k: v for k, v in payload.items() if k != "messages"}
            )
            logger.error(f"scillm-openai call failed after retries: {exc}")
            return {}
