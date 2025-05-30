"""
Tests for the table configuration system.

This module contains tests for the table configuration system, including
presets, configuration parsing, and validation.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from marker.config.table import (
    TableConfig, 
    CamelotConfig, 
    TableOptimizerConfig, 
    TableQualityEvaluatorConfig, 
    TableMergerConfig,
    OptimizationMetric,
    PRESET_HIGH_ACCURACY,
    PRESET_PERFORMANCE,
    PRESET_BALANCED
)
from marker.config.table_parser import parse_table_config, table_config_from_dict


def test_presets_are_valid():
    """Test that the presets are valid TableConfig objects."""
    assert isinstance(PRESET_HIGH_ACCURACY, TableConfig)
    assert isinstance(PRESET_PERFORMANCE, TableConfig)
    assert isinstance(PRESET_BALANCED, TableConfig)


def test_preset_high_accuracy():
    """Test that the high accuracy preset has expected values."""
    preset = PRESET_HIGH_ACCURACY
    
    # Check main settings
    assert preset.use_llm is True
    assert preset.max_rows_per_batch == 60
    
    # Check optimizer settings
    assert preset.optimizer.enabled is True
    assert preset.optimizer.iterations == 5
    assert preset.optimizer.metrics[0] == OptimizationMetric.ACCURACY.value
    
    # Check quality evaluator settings
    assert preset.quality_evaluator.enabled is True
    assert preset.quality_evaluator.min_quality_score == 0.7
    assert preset.quality_evaluator.weights is not None
    assert preset.quality_evaluator.weights["accuracy"] == 0.5
    
    # Check merger settings
    assert preset.merger.enabled is True
    assert preset.merger.use_llm_for_merge_decisions is True


def test_preset_performance():
    """Test that the performance preset has expected values."""
    preset = PRESET_PERFORMANCE
    
    # Check main settings
    assert preset.use_llm is False
    assert preset.max_rows_per_batch == 30
    
    # Check optimizer settings
    assert preset.optimizer.enabled is False
    
    # Check quality evaluator settings
    assert preset.quality_evaluator.enabled is True
    assert preset.quality_evaluator.min_quality_score == 0.5
    assert preset.quality_evaluator.weights is not None
    assert preset.quality_evaluator.weights["speed"] == 0.7
    
    # Check merger settings
    assert preset.merger.enabled is True
    assert preset.merger.use_llm_for_merge_decisions is False


def test_config_serialization_deserialization():
    """Test that a config can be serialized and deserialized."""
    config = PRESET_BALANCED
    
    # Serialize to dict
    config_dict = config.model_dump()
    
    # Deserialize from dict
    new_config = TableConfig(**config_dict)
    
    # Check that the configs are equivalent
    assert new_config.model_dump() == config_dict


def test_config_validation():
    """Test that configuration validation works."""
    # Test invalid weights
    with pytest.raises(ValueError):
        TableQualityEvaluatorConfig(
            evaluation_metrics=["accuracy", "completeness"],
            weights={"accuracy": 0.7}  # Missing weight for completeness
        )
    
    with pytest.raises(ValueError):
        TableQualityEvaluatorConfig(
            evaluation_metrics=["accuracy", "completeness"],
            weights={"accuracy": 0.7, "completeness": 0.7}  # Weights don't sum to 1
        )
    
    # Test duplicate metrics
    with pytest.raises(ValueError):
        TableQualityEvaluatorConfig(
            evaluation_metrics=["accuracy", "accuracy"]  # Duplicate metric
        )


def test_parse_table_config():
    """Test that parse_table_config works with CLI options."""
    # Create CLI options
    cli_options = {
        "table_preset": "balanced",
        "table_enabled": True,
        "camelot_enabled": True,
        "camelot_flavor": "lattice",
        "use_table_optimizer": True,
        "table_optimizer_iterations": 5,
        "use_table_quality_evaluator": True,
        "table_quality_threshold": 0.7,
        "use_table_merger": True,
        "use_llm_for_table_merging": True
    }
    
    # Parse config
    config = parse_table_config(cli_options)
    
    # Check that values were properly parsed
    assert config["enabled"] is True
    assert config["camelot"]["enabled"] is True
    assert config["camelot"]["flavor"] == "lattice"
    assert config["optimizer"]["enabled"] is True
    assert config["optimizer"]["iterations"] == 5
    assert config["quality_evaluator"]["enabled"] is True
    assert config["quality_evaluator"]["min_quality_score"] == 0.7
    assert config["merger"]["enabled"] is True
    assert config["merger"]["use_llm_for_merge_decisions"] is True


def test_table_config_from_json_file():
    """Test that a config can be loaded from a JSON file."""
    # Create a temporary JSON file
    config_dict = {
        "enabled": True,
        "use_llm": True,
        "camelot": {
            "flavor": "stream",
            "min_cell_threshold": 5
        },
        "optimizer": {
            "enabled": True,
            "iterations": 3
        }
    }
    
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as f:
        json.dump(config_dict, f)
        config_path = f.name
    
    try:
        # Create CLI options with the config file
        cli_options = {
            "table_config_json": config_path
        }
        
        # Parse config
        config = parse_table_config(cli_options)
        
        # Check that values from the file were properly parsed
        assert config["enabled"] is True
        assert config["use_llm"] is True
        assert config["camelot"]["flavor"] == "stream"
        assert config["camelot"]["min_cell_threshold"] == 5
        assert config["optimizer"]["enabled"] is True
        assert config["optimizer"]["iterations"] == 3
    finally:
        # Clean up the temporary file
        os.unlink(config_path)


def test_table_config_from_dict():
    """Test that table_config_from_dict creates a valid TableConfig."""
    # Create a config dict
    config_dict = {
        "enabled": True,
        "use_llm": True,
        "camelot": {
            "flavor": "stream",
            "min_cell_threshold": 5
        },
        "optimizer": {
            "enabled": True,
            "iterations": 3
        }
    }
    
    # Convert to TableConfig
    config = table_config_from_dict(config_dict)
    
    # Check that it's a valid TableConfig
    assert isinstance(config, TableConfig)
    assert config.enabled is True
    assert config.use_llm is True
    assert config.camelot.flavor == "stream"
    assert config.camelot.min_cell_threshold == 5
    assert config.optimizer.enabled is True
    assert config.optimizer.iterations == 3


if __name__ == "__main__":
    # Run tests
    import sys
    
    # Track all validation failures
    all_validation_failures = []
    total_tests = 0
    
    # Test 1: Presets are valid
    total_tests += 1
    try:
        test_presets_are_valid()
    except Exception as e:
        all_validation_failures.append(f"test_presets_are_valid: {str(e)}")
    
    # Test 2: High accuracy preset
    total_tests += 1
    try:
        test_preset_high_accuracy()
    except Exception as e:
        all_validation_failures.append(f"test_preset_high_accuracy: {str(e)}")
    
    # Test 3: Performance preset
    total_tests += 1
    try:
        test_preset_performance()
    except Exception as e:
        all_validation_failures.append(f"test_preset_performance: {str(e)}")
    
    # Test 4: Config serialization
    total_tests += 1
    try:
        test_config_serialization_deserialization()
    except Exception as e:
        all_validation_failures.append(f"test_config_serialization_deserialization: {str(e)}")
    
    # Test 5: Config validation
    total_tests += 1
    try:
        test_config_validation()
    except Exception as e:
        all_validation_failures.append(f"test_config_validation: {str(e)}")
    
    # Test 6: Parse table config
    total_tests += 1
    try:
        test_parse_table_config()
    except Exception as e:
        all_validation_failures.append(f"test_parse_table_config: {str(e)}")
    
    # Test 7: Table config from JSON file
    total_tests += 1
    try:
        test_table_config_from_json_file()
    except Exception as e:
        all_validation_failures.append(f"test_table_config_from_json_file: {str(e)}")
    
    # Test 8: Table config from dict
    total_tests += 1
    try:
        test_table_config_from_dict()
    except Exception as e:
        all_validation_failures.append(f"test_table_config_from_dict: {str(e)}")
    
    # Report results
    if all_validation_failures:
        print(f"❌ VALIDATION FAILED - {len(all_validation_failures)} of {total_tests} tests failed:")
        for failure in all_validation_failures:
            print(f"  - {failure}")
        sys.exit(1)
    else:
        print(f"✅ VALIDATION PASSED - All {total_tests} tests produced expected results")
        print("Function is validated and formal tests can now be written")
        sys.exit(0)