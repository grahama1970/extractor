"""
Custom metadata for summarized blocks
"""
from typing import Optional
from marker.schema.blocks.base import BlockMetadata

class SummarizedMetadata(BlockMetadata):
    """Metadata that includes summaries"""
    summary: Optional[str] = None