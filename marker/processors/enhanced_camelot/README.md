# Enhanced Camelot Table Extraction

This module provides enhanced table extraction capabilities using Camelot as a fallback for the primary table extraction mechanism in Marker.

## Features

- **Intelligent Quality Evaluation**: Evaluates table extraction quality using multiple metrics (accuracy, completeness, structure, speed) rather than a simple cell count threshold
- **Parameter Optimization**: Automatically finds the optimal Camelot parameters for each table extraction
- **Table Merging**: Detects and merges tables that span multiple pages or are split into multiple tables
- **Performance Optimization**: Includes caching mechanism to improve performance when processing similar tables

## Configuration

The enhanced Camelot extraction system is highly configurable through the `TableConfig` class, which includes:

```python
from marker.config.table import TableConfig, PRESET_HIGH_ACCURACY

# Use a preset
config = PRESET_HIGH_ACCURACY

# Or create a custom configuration
config = TableConfig(
    camelot=CamelotConfig(
        enabled=True,
        min_cell_threshold=4,
        flavor="lattice"
    ),
    optimizer=TableOptimizerConfig(
        enabled=True,
        iterations=3,
        metrics=["completeness", "accuracy"]
    ),
    quality_evaluator=TableQualityEvaluatorConfig(
        enabled=True,
        min_quality_score=0.6
    ),
    merger=TableMergerConfig(
        enabled=True,
        use_llm_for_merge_decisions=True
    )
)
```

### Configuration Presets

Three presets are available for common use cases:

1. **PRESET_HIGH_ACCURACY**: Optimized for extraction accuracy, using more computation resources
   - Uses LLM for both quality evaluation and merge decisions
   - Tests multiple parameter combinations
   - Prioritizes accuracy over speed

2. **PRESET_PERFORMANCE**: Optimized for speed, using fewer resources
   - Disables parameter optimization
   - Uses heuristics instead of LLMs for merge decisions
   - Prioritizes speed over complete extraction

3. **PRESET_BALANCED**: Balanced approach between accuracy and performance
   - Moderate optimization iterations
   - Uses LLM for critical decisions
   - Balanced weights between accuracy and speed

### Configuration Options

#### Table Optimizer Options

| Option | Description | Default |
|--------|-------------|---------|
| `enabled` | Enable parameter optimization | `False` |
| `iterations` | Number of optimization attempts | `3` |
| `metrics` | Metrics to optimize for | `["completeness", "accuracy"]` |
| `param_space` | Parameter space to search | See default values |
| `timeout` | Max seconds per iteration | `30` |
| `memory_limit_mb` | Memory limit | `4000` |

#### Quality Evaluator Options

| Option | Description | Default |
|--------|-------------|---------|
| `enabled` | Enable quality evaluation | `True` |
| `min_quality_score` | Minimum acceptable score (0-1) | `0.6` |
| `evaluation_metrics` | Metrics to evaluate | `["completeness", "structure"]` |
| `weights` | Metric weights | Equal weights |
| `check_empty_cells` | Check for empty cells | `True` |
| `check_column_alignment` | Check column alignment | `True` |

#### Table Merger Options

| Option | Description | Default |
|--------|-------------|---------|
| `enabled` | Enable table merging | `True` |
| `use_llm_for_merge_decisions` | Use LLM for merge decisions | `True` |
| Various thresholds | Control merge behavior | See documentation |

## Usage

The enhanced Camelot functionality is integrated with the standard table processor and can be enabled through configuration:

```python
from marker.processors.table import TableProcessor
from marker.config.table import PRESET_HIGH_ACCURACY

# Create table processor with enhanced camelot enabled
processor = TableProcessor(config=PRESET_HIGH_ACCURACY)

# Process document normally - enhanced camelot will be used automatically when needed
processor.process(document)
```

Or via command line:

```bash
python -m marker.scripts.convert input.pdf --table-preset=high_accuracy
```

## Advanced Usage

For more advanced usage, see the individual component classes:

- `TableQualityEvaluator`: For evaluating table extraction quality
- `ParameterOptimizer`: For finding optimal Camelot parameters
- `TableMerger`: For handling tables that span multiple pages

Each component can be used independently or together through the enhanced processor.