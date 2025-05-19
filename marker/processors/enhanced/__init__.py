"""
Enhanced processors for Marker

These processors extend the base functionality with additional features:
- Enhanced table extraction with Camelot integration
- Section summarization with LLM support
- Document hierarchy building
"""

from marker.processors.enhanced.enhanced_table_simple import SimpleEnhancedTableProcessor
from marker.processors.enhanced.summarizer import SectionSummarizer
from marker.processors.enhanced.hierarchy_builder import HierarchyBuilder

__all__ = [
    'SimpleEnhancedTableProcessor',
    'SectionSummarizer', 
    'HierarchyBuilder'
]