# Enhanced Table Extraction in Marker

This document explains the enhanced table extraction capabilities in Marker, including configuration options, presets, and best practices.

## Overview

Marker includes a comprehensive table extraction system that combines multiple approaches:

1. **Primary extraction**: Uses neural models to detect and recognize tables
2. **Quality evaluation**: Assesses extraction quality to determine if fallback methods are needed
3. **Parameter optimization**: Automatically tunes extraction parameters for best results
4. **Camelot fallback**: Uses the Camelot library for traditional table extraction when needed
5. **Table merging**: Combines tables that span multiple pages or columns

## Configuration Options

The table extraction system is highly configurable through a unified `TableConfig` object with nested configuration sections for different components.

### Using Presets

Three built-in presets are available:

- `high_accuracy`: Prioritizes accuracy over performance
- `performance`: Prioritizes speed over accuracy
- `balanced`: Provides a balanced approach (default)

You can use these presets via command line:

```bash
python convert.py input.pdf --table-preset high_accuracy
python convert.py input.pdf --table-preset performance
python convert.py input.pdf --table-preset balanced
```

### Main Table Configuration

The main table configuration controls general table processing settings:

| Option | Description | Default |
| ------ | ----------- | ------- |
| `enabled` | Enable/disable table processing | `true` |
| `use_llm` | Use LLM for improving table extraction | `false` |
| `max_rows_per_batch` | Maximum number of rows to process in a batch | `60` |
| `max_table_rows` | Maximum rows in a table to process with LLM | `175` |
| `detection_batch_size` | Batch size for table detection model | `null` (auto) |
| `table_rec_batch_size` | Batch size for table recognition model | `null` (auto) |
| `recognition_batch_size` | Batch size for text recognition | `null` (auto) |
| `disable_tqdm` | Disable progress bars | `false` |

### Camelot Configuration

The Camelot configuration controls the fallback table extraction:

| Option | Description | Default |
| ------ | ----------- | ------- |
| `enabled` | Enable/disable Camelot fallback | `true` |
| `min_cell_threshold` | Minimum cells needed for valid extraction | `4` |
| `flavor` | Extraction mode (`"lattice"`, `"stream"`, `"auto"`) | `"auto"` |
| `line_width` | Width parameter for detecting table lines | `15` |
| `line_scale` | Scale parameter for detecting table lines | `40` |
| `copy_text` | Copy text from PDF or use OCR | `true` |
| `infer_cell_borders` | Infer borders when not visible | `true` |
| `edge_tol` | Tolerance for extending edges in lattice mode | `50` |
| `row_tol` | Tolerance for extending rows in stream mode | `2` |

### Optimizer Configuration

The optimizer configuration controls automatic parameter tuning:

| Option | Description | Default |
| ------ | ----------- | ------- |
| `enabled` | Enable/disable parameter optimization | `false` |
| `iterations` | Number of optimization iterations | `3` |
| `metrics` | Metrics to optimize for, in priority order | `["completeness", "accuracy"]` |
| `timeout` | Timeout in seconds for each iteration | `30` |
| `memory_limit_mb` | Memory limit for optimization | `4000` |

### Quality Evaluator Configuration

The quality evaluator configuration controls how table quality is assessed:

| Option | Description | Default |
| ------ | ----------- | ------- |
| `enabled` | Enable/disable quality evaluation | `true` |
| `min_quality_score` | Minimum score (0-1) to accept extraction | `0.6` |
| `evaluation_metrics` | Metrics used for evaluation | `["completeness", "structure"]` |
| `weights` | Relative weights for metrics | `null` (equal) |
| `check_empty_cells` | Check for empty cells in quality assessment | `true` |
| `check_column_alignment` | Check column alignment in quality assessment | `true` |

### Merger Configuration

The merger configuration controls how tables are combined:

| Option | Description | Default |
| ------ | ----------- | ------- |
| `enabled` | Enable/disable table merging | `true` |
| `table_height_threshold` | Minimum height ratio for merging | `0.6` |
| `table_start_threshold` | Maximum % down page for merge consideration | `0.2` |
| `vertical_table_height_threshold` | Height tolerance for vertical merging | `0.25` |
| `vertical_table_distance_threshold` | Max distance for vertical adjacency | `20` |
| `horizontal_table_width_threshold` | Width tolerance for horizontal merging | `0.25` |
| `horizontal_table_distance_threshold` | Max distance for horizontal adjacency | `10` |
| `column_gap_threshold` | Max gap between columns to merge | `50` |
| `row_split_threshold` | % of rows for row splitting | `0.5` |
| `use_llm_for_merge_decisions` | Use LLM to decide on merging | `true` |

## Using a Custom Configuration File

You can provide a custom configuration file in JSON format:

```bash
python convert.py input.pdf --table-config-json myconfig.json
```

Example JSON configuration:

```json
{
  "enabled": true,
  "use_llm": true,
  "camelot": {
    "enabled": true,
    "flavor": "auto"
  },
  "optimizer": {
    "enabled": true,
    "iterations": 5
  }
}
```

## Best Practices

### For Accurate Table Extraction

1. Start with the `high_accuracy` preset
2. Enable the optimizer with metrics focused on accuracy and completeness
3. Use LLM-based table processing for complex or poorly formatted tables
4. Enable table merging with LLM-based decisions

### For Fast Processing

1. Use the `performance` preset
2. Disable the optimizer or limit to 1-2 iterations
3. Specify smaller batch sizes for lower memory usage
4. Disable LLM-based processing for faster extraction

### For Specific Table Types

- **Tables with borders**: Use Camelot with `"lattice"` flavor and higher line width (15-20)
- **Tables without borders**: Use Camelot with `"stream"` flavor and lower row tolerance
- **Complex merged tables**: Enable the merger and use LLM for merge decisions
- **Tables with multiline cells**: Set appropriate row split threshold (0.5-0.7)

## Advanced Usage

### Programmatic Configuration

You can create and customize a `TableConfig` object in code:

```python
from marker.config.table import TableConfig, CamelotConfig, PRESET_HIGH_ACCURACY

# Start with a preset
config = PRESET_HIGH_ACCURACY.copy(deep=True)

# Customize specific settings
config.camelot.flavor = "lattice"
config.camelot.line_width = 20
config.optimizer.enabled = True
config.optimizer.iterations = 5

# Use the configuration
converter = PdfConverter(
    artifact_dict,
    config={"table": config.dict()}
)
```

### Per-Document Configuration

For batch processing with different settings per document:

```python
for filepath in files:
    # Determine document type and select appropriate config
    if "financial_report" in filepath:
        table_config = PRESET_HIGH_ACCURACY.copy(deep=True)
    elif "newsletter" in filepath:
        table_config = PRESET_PERFORMANCE.copy(deep=True)
    else:
        table_config = PRESET_BALANCED.copy(deep=True)
    
    # Process with document-specific config
    converter = PdfConverter(
        artifact_dict,
        config={"table": table_config.dict()}
    )
    result = converter(filepath)
```

## Troubleshooting

### Common Issues

1. **Poor Table Extraction**: Try enabling the optimizer and increasing iterations
2. **Slow Processing**: Reduce batch sizes or use the performance preset
3. **Memory Errors**: Lower batch sizes and set memory limits in optimizer
4. **Missing Table Content**: Try alternate Camelot flavors or adjust line parameters
5. **Tables Not Detected**: Ensure tables are properly identified in layout stage

### Debug Options

You can enable debug mode to visualize table extraction:

```bash
python convert.py input.pdf --debug
```

This will output:
- PDF images with identified tables
- Layout images with table blocks
- JSON representation of table structure
- Visualization of extracted cells

## Further Reading

- [Camelot Documentation](https://camelot-py.readthedocs.io/)
- [Table Extraction Best Practices](https://github.com/camelot-dev/camelot/wiki/Best-Practices)
- [Marker Table Processing](../marker/processors/table.py)
- [EnhancedTableProcessor](../marker/processors/enhanced_table.py)