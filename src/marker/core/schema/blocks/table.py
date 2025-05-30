from typing import Optional, Dict, Any, List
from pydantic import Field

from marker.core.schema import BlockTypes
from marker.core.schema.blocks.basetable import BaseTable


class Table(BaseTable):
    block_type: BlockTypes = BlockTypes.Table
    block_description: str = "A table of data, like a results table.  It will be in a tabular format."
    
    # Extraction metadata
    extraction_method: Optional[str] = Field(None, description="Method used to extract table (surya, camelot)")
    extraction_details: Optional[Dict[str, Any]] = Field(None, description="Detailed extraction parameters")
    
    # Quality metrics
    quality_score: Optional[float] = Field(None, description="Overall quality score (0-100)")
    quality_metrics: Optional[Dict[str, float]] = Field(None, description="Detailed quality metrics")
    
    # Merge information
    merge_info: Optional[Dict[str, Any]] = Field(None, description="Information about table merging")
    
    def update_extraction_metadata(self, method: str, details: Optional[Dict[str, Any]] = None):
        """Update extraction method and details."""
        self.extraction_method = method
        self.extraction_details = details or {}
    
    def update_quality_metrics(self, score: float, metrics: Optional[Dict[str, float]] = None):
        """Update quality score and metrics."""
        self.quality_score = score
        self.quality_metrics = metrics or {}
    
    def update_merge_info(self, merge_type: str, original_tables: List[Dict[str, Any]], 
                         confidence: Optional[float] = None, merge_method: Optional[str] = None):
        """Update merge information with original table data."""
        self.merge_info = {
            "merge_type": merge_type,  # vertical, horizontal, across_pages
            "merge_method": merge_method or "heuristic",  # heuristic, llm
            "merge_confidence": confidence,
            "original_tables": original_tables,
            "original_count": len(original_tables)
        }
