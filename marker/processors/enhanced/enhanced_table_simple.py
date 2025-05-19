"""
Simplified Enhanced Table Processor

Provides enhanced table extraction with minimal configuration.
"""

from typing import Optional
from marker.processors.table import TableProcessor
from marker.schema.document import Document
from marker.processors.table_optimizer import TableOptimizer


class SimpleEnhancedTableProcessor(TableProcessor):
    """
    Enhanced table processor with simplified configuration.
    
    Extends the base table processor with optional optimization.
    """
    
    def __init__(self, *args, optimize_tables: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.optimize_tables = optimize_tables
        if optimize_tables:
            self.optimizer = TableOptimizer()
    
    def __call__(self, document: Document) -> Document:
        """Process tables with optional optimization."""
        # Run base table processing
        document = super().__call__(document)
        
        # Optionally optimize tables
        if self.optimize_tables and hasattr(self, 'optimizer'):
            for page in document.pages:
                for table in page.contained_blocks(document, [BlockTypes.Table]):
                    self.optimizer.optimize_table(table)
        
        return document