"""
Simplified table configuration for Marker.
Module: table_simple.py

Provides simple presets for table extraction with sensible defaults.
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class SimpleTableConfig(BaseModel):
    """Simple table configuration with essential settings only."""
    
    # Core settings
    enabled: bool = True
    min_cells: int = 4  # Minimum cells to consider it a table
    
    # Quality thresholds
    min_quality_score: float = 0.6
    
    # Camelot settings (when used)
    use_camelot_fallback: bool = True
    camelot_flavor: str = "auto"  # "lattice", "stream", or "auto"
    
    # Optimization
    optimize_params: bool = False
    max_iterations: int = 3


# Presets for common use cases
PRESET_FAST = SimpleTableConfig(
    optimize_params=False,
    use_camelot_fallback=False
)

PRESET_BALANCED = SimpleTableConfig(
    optimize_params=True,
    max_iterations=3
)

PRESET_HIGH_QUALITY = SimpleTableConfig(
    optimize_params=True,
    max_iterations=5,
    min_quality_score=0.8,
    use_camelot_fallback=True
)