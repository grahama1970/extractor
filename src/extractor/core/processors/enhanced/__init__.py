"""
Enhanced processors for Marker
Module: __init__.py
Description: Package initialization and exports

These processors extend the base functionality with additional features:
- Enhanced table extraction with Camelot integration
- Section summarization with LLM support
- Document hierarchy building
"""

from extractor.core.processors.enhanced.enhanced_table_simple import SimpleEnhancedTableProcessor
from extractor.core.processors.enhanced.summarizer import SectionSummarizer
from extractor.core.processors.enhanced.hierarchy_builder import HierarchyBuilder

__all__ = [
    'SimpleEnhancedTableProcessor',
    'SectionSummarizer', 
    'HierarchyBuilder'
]