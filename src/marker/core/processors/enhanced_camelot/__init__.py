"""
Enhanced Camelot table extraction module for Marker.

This module provides enhanced Camelot table extraction for Marker, with quality evaluation,
parameter optimization, and table merging capabilities. It is designed to handle complex
tables and tables that span multiple pages, producing higher-quality output.

Usage example:
```python
from marker.core.processors.enhanced_camelot import EnhancedTableProcessor

processor = EnhancedTableProcessor(
    detection_model,
    recognition_model,
    table_rec_model,
    config={"use_enhanced_camelot": True, "use_table_merging": True}
)
processor(document)
```

References:
- Camelot documentation: https://camelot-py.readthedocs.io/en/master/
- pandas documentation: https://pandas.pydata.org/docs/
"""

from marker.core.processors.enhanced_camelot.processor import EnhancedTableProcessor
from marker.core.utils.table_quality_evaluator import TableQualityEvaluator
from marker.core.utils.table_comparison import (
    compare_table_structure,
    compare_table_content,
    compare_table_position,
    should_merge_tables,
    calculate_iou
)
from marker.core.utils.table_merger import TableMerger

__all__ = [
    'EnhancedTableProcessor',
    'TableQualityEvaluator',
    'TableMerger',
    'compare_table_structure',
    'compare_table_content',
    'compare_table_position',
    'should_merge_tables',
    'calculate_iou'
]