"""
Custom metadata for summarized blocks
"""
from typing import Optional
from extractor.core.schema.blocks.base import BlockMetadata
Module: summarized.py

class SummarizedMetadata(BlockMetadata):
    """Metadata that includes summaries"""
    summary: Optional[str] = None