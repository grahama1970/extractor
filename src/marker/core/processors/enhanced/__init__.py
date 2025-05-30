"""
Enhanced processors for Marker

These processors extend the base functionality with additional features:
- Enhanced table extraction with Camelot integration
- Section summarization with LLM support
- Document hierarchy building
"""

from marker.core.processors.enhanced.enhanced_table_simple import SimpleEnhancedTableProcessor
from marker.core.processors.enhanced.summarizer import SectionSummarizer
from marker.core.processors.enhanced.hierarchy_builder import HierarchyBuilder

__all__ = [
    'SimpleEnhancedTableProcessor',
    'SectionSummarizer', 
    'HierarchyBuilder'
]