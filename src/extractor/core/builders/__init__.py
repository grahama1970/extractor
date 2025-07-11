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

from typing import Optional

from pydantic import BaseModel

from extractor.core.util import assign_config


class BaseBuilder:
    def __init__(self, config: Optional[BaseModel | dict] = None):
        assign_config(self, config)

    def __call__(self, data, *args, **kwargs):
        raise NotImplementedError
