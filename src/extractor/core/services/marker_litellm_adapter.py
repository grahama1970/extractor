#!/usr/bin/env python3
"""
LiteLLM adapter for Marker - provides BaseService interface using LiteLLM.
This is a minimal wrapper that preserves Marker's original architecture.
"""

from typing import Any, Dict, Optional
from PIL import Image
import base64
import io

from extractor.core.services import BaseService
from extractor.core.services.litellm import LiteLLMService
from extractor.pipeline.utils.litellm_response_utils import extract_content


class MarkerLiteLLMAdapter(BaseService):
    """Adapter that makes LiteLLMService work with Marker's original LLM processors."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

        # Initialize the underlying LiteLLM service
        self.litellm_service = LiteLLMService(config)

        # Copy over the model name from config
        self.model_name = config.get("model", "gpt-3.5-turbo")

    def __call__(self, prompt: str, image: Image.Image, block: Any, schema: Any) -> Dict[str, Any]:
        """
        Call the LLM with the original Marker interface.
        This matches what Marker's LLM processors expect.
        """
        try:
            # Convert PIL image to base64 for LiteLLM
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            image_base64 = base64.b64encode(buffered.getvalue()).decode()

            # Create messages in LiteLLM format
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                        },
                    ],
                }
            ]

            # Call through the underlying service (now backed by scillm/openai-http)
            result = self.litellm_service(
                prompt=prompt,
                image=image,
                block=block,
                response_schema=schema,
            )
            return {"result": result}

        except Exception as e:
            print(f"LiteLLM call failed: {e}")
            # Return empty result on failure
            return {}

    # Add methods that Marker's BaseService expects
    def img_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string."""
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()

    def process_images(self, images: list) -> list:
        """Process multiple images (placeholder for compatibility)."""
        return images

    def format_image_for_llm(self, image: Image.Image) -> Dict[str, Any]:
        """Format image for LLM input."""
        return {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{self.img_to_base64(image)}"},
        }
