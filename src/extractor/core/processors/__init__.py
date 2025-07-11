"""
Module: __init__.py
Description: Package initialization and exports

External Dependencies:
- pydantic: https://docs.pydantic.dev/
- marker: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

from typing import Optional, Tuple

from pydantic import BaseModel

from extractor.core.schema import BlockTypes
from extractor.core.schema.document import Document
from extractor.core.util import assign_config


class BaseProcessor:
    block_types: Tuple[BlockTypes] | None = None  # What block types this processor is responsible for

    def __init__(self, config: Optional[BaseModel | dict] = None):
        assign_config(self, config)

    def __call__(self, document: Document, *args, **kwargs):
        raise NotImplementedError
