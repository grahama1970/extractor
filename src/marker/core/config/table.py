"""
Simplified table configuration for Marker
"""
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any
from pydantic import BaseModel, Field


class OptimizationMetric(str, Enum):
    """Metrics for table optimization"""
    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    STRUCTURE = "structure"
    SPEED = "speed"
    COMBINED = "combined"


class TableOptimizerConfig(BaseModel):
    """Configuration for table parameter optimization"""
    enabled: bool = Field(default=False, description="Enable table parameter optimization")
    
    # Parameter ranges for optimization
    line_scale_range: Tuple[int, int] = Field(default=(15, 50), description="Range for Camelot line_scale parameter")
    line_width_range: Tuple[int, int] = Field(default=(1, 5), description="Range for Camelot line_width parameter")
    shift_text_values: List[bool] = Field(default=[True, False], description="Values for shift_text parameter")
    split_text_values: List[bool] = Field(default=[True, False], description="Values for split_text parameter")
    
    # Optimization settings
    optimization_metric: OptimizationMetric = Field(default=OptimizationMetric.COMBINED, description="Metric to optimize for")
    max_iterations: int = Field(default=20, description="Maximum iterations for optimization")
    iterations: int = Field(default=10, description="Number of iterations for finding best params")
    early_stop_threshold: float = Field(default=0.95, description="Stop if score reaches this threshold")
    
    # Parallel processing
    n_workers: int = Field(default=4, description="Number of parallel workers")
    timeout_seconds: int = Field(default=30, description="Timeout per extraction attempt")


class CamelotConfig(BaseModel):
    """Configuration for Camelot table extraction"""
    flavor: str = Field(default='lattice', description="Camelot extraction flavor (lattice or stream)")
    line_scale: int = Field(default=40, description="Line scale parameter for lattice flavor")
    line_width: int = Field(default=3, description="Line width parameter for lattice flavor")
    shift_text: bool = Field(default=True, description="Shift text within cells")
    split_text: bool = Field(default=True, description="Split text at column boundaries")
    strip_text: str = Field(default=r'\n', description="Characters to strip from cell text")
    edge_tol: int = Field(default=50, description="Edge tolerance for table detection")
    row_tol: int = Field(default=2, description="Row tolerance for table detection")
    column_tol: int = Field(default=0, description="Column tolerance for table detection")
    infer_cell_borders: bool = Field(default=False, description="Infer cell borders for stream flavor")


class TableQualityEvaluatorConfig(BaseModel):
    """Configuration for table quality evaluation"""
    enabled: bool = Field(default=True, description="Enable table quality evaluation")
    min_cells: int = Field(default=4, description="Minimum cells for valid table")
    max_empty_ratio: float = Field(default=0.8, description="Maximum ratio of empty cells")
    min_structure_score: float = Field(default=0.5, description="Minimum structure score")
    min_quality_score: float = Field(default=0.6, description="Minimum quality score threshold")
    
    # Metric weights
    completeness_weight: float = Field(default=0.25, description="Weight for completeness metric")
    accuracy_weight: float = Field(default=0.25, description="Weight for accuracy metric")
    structure_weight: float = Field(default=0.25, description="Weight for structure metric")
    consistency_weight: float = Field(default=0.25, description="Weight for consistency metric")
    
    # Evaluation metrics
    evaluation_metrics: List[str] = Field(
        default=["completeness", "accuracy", "structure", "consistency"],
        description="Metrics to evaluate"
    )
    weights: Dict[str, float] = Field(
        default={"completeness": 0.25, "accuracy": 0.25, "structure": 0.25, "consistency": 0.25},
        description="Weights for metrics"
    )
    
    # Structure evaluation options
    check_column_alignment: bool = Field(default=True, description="Check column alignment in structure score")
    check_empty_cells: bool = Field(default=True, description="Check empty cells in structure score")


class TableMergerConfig(BaseModel):
    """Configuration for table merging"""
    enabled: bool = Field(default=True, description="Enable table merging")
    max_vertical_gap: float = Field(default=10.0, description="Maximum vertical gap between tables to merge")
    min_column_overlap: float = Field(default=0.8, description="Minimum column overlap ratio")
    merge_across_pages: bool = Field(default=True, description="Allow merging tables across pages")
    preserve_original: bool = Field(default=True, description="Preserve original tables in merge_info")
    
    # Thresholds from enhanced_camelot
    table_height_threshold: float = Field(default=0.5, description="Table height threshold for merging")
    table_start_threshold: float = Field(default=0.1, description="Table start position threshold")
    vertical_table_height_threshold: float = Field(default=0.5, description="Vertical table height threshold")
    vertical_table_distance_threshold: float = Field(default=0.1, description="Vertical table distance threshold")
    horizontal_table_width_threshold: float = Field(default=0.5, description="Horizontal table width threshold")
    horizontal_table_distance_threshold: float = Field(default=0.1, description="Horizontal table distance threshold")
    column_gap_threshold: float = Field(default=0.1, description="Column gap threshold")
    row_split_threshold: float = Field(default=0.2, description="Row split threshold")
    
    # LLM options
    use_llm_for_merge_decisions: bool = Field(default=False, description="Use LLM to assist with merge decisions")


class TableConfig(BaseModel):
    """Enhanced table configuration with all sub-configurations"""
    enabled: bool = True
    min_cells: int = 4
    use_camelot_fallback: bool = True
    optimize: bool = False
    use_llm: bool = False
    
    # Quality settings
    min_quality_score: float = 0.6
    
    # Nested configurations
    camelot: Optional[CamelotConfig] = None
    optimizer: Optional[TableOptimizerConfig] = None
    quality_evaluator: Optional[TableQualityEvaluatorConfig] = None
    merger: Optional[TableMergerConfig] = None
    
    class Config:
        extra = 'allow'  # Allow additional fields for flexibility
    
    def __init__(self, **kwargs):
        """Initialize with proper defaults for nested configs"""
        super().__init__(**kwargs)
        
        # Initialize nested configs with defaults if not provided
        if self.camelot is None:
            self.camelot = CamelotConfig()
        if self.optimizer is None:
            self.optimizer = TableOptimizerConfig()
        if self.quality_evaluator is None:
            self.quality_evaluator = TableQualityEvaluatorConfig()
        if self.merger is None:
            self.merger = TableMergerConfig()


# Extended presets with full configurations
TABLE_FAST = TableConfig(
    optimize=False, 
    use_camelot_fallback=False,
    quality_evaluator=TableQualityEvaluatorConfig(enabled=False),
    optimizer=TableOptimizerConfig(enabled=False),
    merger=TableMergerConfig(enabled=False)
)

TABLE_BALANCED = TableConfig(
    optimize=True,
    use_camelot_fallback=True,
    quality_evaluator=TableQualityEvaluatorConfig(enabled=True),
    optimizer=TableOptimizerConfig(enabled=True, max_iterations=10),
    merger=TableMergerConfig(enabled=True)
)

TABLE_HIGH_QUALITY = TableConfig(
    optimize=True, 
    min_quality_score=0.8,
    use_camelot_fallback=True,
    quality_evaluator=TableQualityEvaluatorConfig(enabled=True, min_structure_score=0.7),
    optimizer=TableOptimizerConfig(enabled=True, max_iterations=20),
    merger=TableMergerConfig(enabled=True, merge_across_pages=True)
)

# Legacy preset names for compatibility
PRESET_BALANCED = TABLE_BALANCED


def table_config_from_dict(config_dict: Dict[str, Any]) -> TableConfig:
    """Convert a dictionary to a TableConfig object"""
    return TableConfig(**config_dict)