# Enhanced Camelot Table Extraction

The Enhanced Camelot Table Extraction functionality has been implemented and integrated. It provides the following features:

## Features
- Quality evaluation based on multiple metrics
- Parameter optimization to find the best extraction settings
- Table merging for tables that span multiple pages
- Customizable configuration with presets

## Usage
To use the enhanced Camelot table extraction, you can use the `--table-preset` option with the `convert` or `convert_single` scripts:

```
python marker/scripts/convert_single.py input.pdf --table-preset=high_accuracy
```

Available presets:
- `high_accuracy` - Best quality, more compute resources
- `balanced` - Good balance of quality and performance
- `performance` - Fastest processing with basic quality

## Configuration
For more detailed configuration, you can create a custom JSON configuration file:

```json
{
  "table": {
    "camelot": {
      "enabled": true,
      "flavor": "auto"
    },
    "optimizer": {
      "enabled": true,
      "iterations": 5
    },
    "quality_evaluator": {
      "enabled": true,
      "min_quality_score": 0.7
    },
    "merger": {
      "enabled": true
    }
  }
}
```

And use it with:
```
python marker/scripts/convert_single.py input.pdf --config_json=config.json
```

## Debugging
For debugging, you can check the debug output in the `debug_output` directory, or add debug flags:
```
python marker/scripts/convert_single.py input.pdf --table-preset=high_accuracy --debug
```