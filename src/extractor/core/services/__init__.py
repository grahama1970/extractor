"""
Module: __init__.py
Description: Package initialization and exports

External Dependencies:
- PIL: [Documentation URL]
- pydantic: https://docs.pydantic.dev/
- marker: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

from typing import Optional, List, Annotated

import PIL
from pydantic import BaseModel

from extractor.core.schema.blocks import Block
from extractor.core.util import assign_config, verify_config_keys


class BaseService:
    timeout: Annotated[
        int,
        "The timeout to use for the service."
    ] = 30
    max_retries: Annotated[
        int,
        "The maximum number of retries to use for the service."
    ] = 2

    def __init__(self, config: Optional[BaseModel | dict] = None):
        assign_config(self, config)

        # Ensure we have all necessary fields filled out (API keys, etc.)
        verify_config_keys(self)

    def __call__(
        self,
        prompt: str,
        image: PIL.Image.Image | List[PIL.Image.Image],
        block: Block,
        response_schema: type[BaseModel],
        max_retries: int | None = None,
        timeout: int | None = None
     ):
        raise NotImplementedError

# Import services for module-level access
from extractor.core.services.litellm import LiteLLMService