"""
Simplified table configuration for Marker
"""
from pydantic import BaseModel, Field


class TableConfig(BaseModel):
    """Simple table configuration"""
    enabled: bool = True
    min_cells: int = 4
    use_camelot_fallback: bool = True
    optimize: bool = False
    
    # Quality settings
    min_quality_score: float = 0.6
    
    class Config:
        extra = 'allow'  # Allow additional fields for flexibility


# Simple presets
TABLE_FAST = TableConfig(optimize=False, use_camelot_fallback=False)
TABLE_BALANCED = TableConfig(optimize=True)
TABLE_HIGH_QUALITY = TableConfig(optimize=True, min_quality_score=0.8)