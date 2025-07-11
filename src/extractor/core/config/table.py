"""
Module: table.py
Description: Simplified table configuration for Marker

External Dependencies:
- pydantic: https://docs.pydantic.dev/
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
    
    # LLM merge validation
    use_llm_for_merge_decisions: bool = Field(default=True, description="Use LLM to validate merge decisions")
    llm_confidence_threshold: float = Field(default=0.8, description="LLM confidence threshold for merging")


class TableExtractionMethod(str, Enum):
    """Available table extraction methods"""
    ENHANCED_CAMELOT = "enhanced_camelot"
    MARKER = "marker"
    SURYA = "surya"
    CAMELOT = "camelot"
    FALLBACK = "fallback"


class TableConfig(BaseModel):
    """Master configuration for table extraction"""
    enabled: bool = Field(default=True, description="Enable table extraction")
    extraction_method: TableExtractionMethod = Field(
        default=TableExtractionMethod.ENHANCED_CAMELOT,
        description="Primary extraction method"
    )
    fallback_methods: List[TableExtractionMethod] = Field(
        default=[TableExtractionMethod.MARKER, TableExtractionMethod.CAMELOT],
        description="Fallback methods if primary fails"
    )
    
    # Sub-configurations
    camelot: CamelotConfig = Field(default_factory=CamelotConfig)
    quality_evaluator: TableQualityEvaluatorConfig = Field(default_factory=TableQualityEvaluatorConfig)
    merger: TableMergerConfig = Field(default_factory=TableMergerConfig)
    optimizer: TableOptimizerConfig = Field(default_factory=TableOptimizerConfig)
    
    # Advanced settings
    min_table_size: int = Field(default=100, description="Minimum pixels for table detection")
    max_table_size: int = Field(default=10000, description="Maximum pixels for table detection")
    ocr_confidence_threshold: float = Field(default=0.6, description="OCR confidence for table cells")
    use_gpu: bool = Field(default=True, description="Use GPU for table detection if available")
    preserve_formatting: bool = Field(default=True, description="Preserve cell formatting")
    extract_headers: bool = Field(default=True, description="Attempt to identify table headers")
    
    # Batch processing
    batch_size: int = Field(default=5, description="Number of tables to process in parallel")
    timeout_per_table: int = Field(default=60, description="Timeout per table in seconds")
    
    # Output options
    output_format: str = Field(default="cells", description="Output format: cells, df, html, csv")
    include_metadata: bool = Field(default=True, description="Include extraction metadata")


# Export convenience presets
TABLE_CONFIG_PRESETS = {
    "high_accuracy": TableConfig(
        extraction_method=TableExtractionMethod.ENHANCED_CAMELOT,
        quality_evaluator=TableQualityEvaluatorConfig(
            min_quality_score=0.8,
            enabled=True
        ),
        optimizer=TableOptimizerConfig(
            enabled=True,
            optimization_metric=OptimizationMetric.ACCURACY
        )
    ),
    "fast": TableConfig(
        extraction_method=TableExtractionMethod.MARKER,
        quality_evaluator=TableQualityEvaluatorConfig(enabled=False),
        optimizer=TableOptimizerConfig(enabled=False),
        batch_size=10
    ),
    "balanced": TableConfig()  # Use defaults
}


if __name__ == "__main__":
    """Validation function for table configuration"""
    # Test configuration creation
    config = TableConfig()
    print(f"✅ Default TableConfig created successfully")
    
    # Test preset loading
    for preset_name, preset_config in TABLE_CONFIG_PRESETS.items():
        print(f"✅ Preset '{preset_name}' loaded successfully")
        
    # Test serialization
    config_dict = config.model_dump()
    config_json = config.model_dump_json(indent=2)
    print(f"✅ Configuration serialization successful")
    
    # Test field access
    print(f"  - Extraction method: {config.extraction_method}")
    print(f"  - Quality threshold: {config.quality_evaluator.min_quality_score}")
    print(f"  - Camelot flavor: {config.camelot.flavor}")
    
    print("\n✅ Table configuration validation passed!")