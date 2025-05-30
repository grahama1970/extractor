"""Utility functions for the LLM call module.

Provides helper functions for configuration, validation, and report generation.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from loguru import logger

from marker.core.llm_call.core.debug import ValidationTrace


def load_config(path: Union[str, Path]) -> Dict[str, Any]:
    """Load configuration from JSON or YAML file.
    
    Args:
        path: Path to configuration file
        
    Returns:
        Configuration dictionary
        
    Raises:
        ValueError: If file format is not supported
    """
    path = Path(path)
    
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    
    if path.suffix.lower() in ['.json']:
        with open(path, 'r') as f:
            return json.load(f)
    elif path.suffix.lower() in ['.yaml', '.yml']:
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    else:
        raise ValueError(f"Unsupported configuration format: {path.suffix}")


def save_validation_report(
    traces: List[ValidationTrace],
    path: Union[str, Path],
    format: str = "json"
) -> None:
    """Save validation traces to a report file.
    
    Args:
        traces: List of validation traces
        path: Path to save the report
        format: Report format (json, yaml, or markdown)
    """
    path = Path(path)
    
    # Prepare report data
    report = {
        "timestamp": datetime.now().isoformat(),
        "version": "1.0",
        "summary": _create_summary(traces),
        "traces": [trace.to_dict() for trace in traces]
    }
    
    if format == "json":
        with open(path, 'w') as f:
            json.dump(report, f, indent=2)
    
    elif format == "yaml":
        with open(path, 'w') as f:
            yaml.dump(report, f, default_flow_style=False)
    
    elif format == "markdown":
        with open(path, 'w') as f:
            f.write(_create_markdown_report(report))
    
    else:
        raise ValueError(f"Unsupported report format: {format}")
    
    logger.info(f"Saved validation report to: {path}")


def _create_summary(traces: List[ValidationTrace]) -> Dict[str, Any]:
    """Create a summary from validation traces."""
    total_traces = len(traces)
    successful_traces = sum(1 for trace in traces if trace.result and trace.result.valid)
    
    # Calculate total duration
    total_duration = 0.0
    for trace in traces:
        total_duration += trace.duration_ms
    
    # Find longest running trace
    longest_trace = max(traces, key=lambda t: t.duration_ms) if traces else None
    
    # Count by strategy
    strategy_counts = {}
    for trace in traces:
        strategy_name = trace.strategy_name
        if strategy_name not in strategy_counts:
            strategy_counts[strategy_name] = {"total": 0, "successful": 0}
        
        strategy_counts[strategy_name]["total"] += 1
        if trace.result and trace.result.valid:
            strategy_counts[strategy_name]["successful"] += 1
    
    return {
        "total_traces": total_traces,
        "successful_traces": successful_traces,
        "success_rate": successful_traces / total_traces if total_traces > 0 else 0,
        "total_duration_ms": total_duration,
        "average_duration_ms": total_duration / total_traces if total_traces > 0 else 0,
        "longest_trace": {
            "strategy": longest_trace.strategy_name,
            "duration_ms": longest_trace.duration_ms
        } if longest_trace else None,
        "strategy_counts": strategy_counts
    }


def _create_markdown_report(report: Dict[str, Any]) -> str:
    """Create a markdown formatted report."""
    lines = []
    
    # Header
    lines.append("# LLM Validation Report")
    lines.append(f"\n**Generated**: {report['timestamp']}")
    lines.append(f"**Version**: {report['version']}")
    
    # Summary
    summary = report['summary']
    lines.append("\n## Summary")
    lines.append(f"- **Total Validations**: {summary['total_traces']}")
    lines.append(f"- **Successful**: {summary['successful_traces']}")
    lines.append(f"- **Success Rate**: {summary['success_rate']:.1%}")
    lines.append(f"- **Total Duration**: {summary['total_duration_ms']:.2f}ms")
    lines.append(f"- **Average Duration**: {summary['average_duration_ms']:.2f}ms")
    
    if summary['longest_trace']:
        lines.append(f"- **Longest Validation**: {summary['longest_trace']['strategy']} "
                    f"({summary['longest_trace']['duration_ms']:.2f}ms)")
    
    # Strategy breakdown
    if summary['strategy_counts']:
        lines.append("\n### Strategy Performance")
        lines.append("| Strategy | Total | Successful | Success Rate |")
        lines.append("|----------|-------|------------|--------------|")
        
        for strategy, counts in summary['strategy_counts'].items():
            total = counts['total']
            successful = counts['successful']
            rate = successful / total if total > 0 else 0
            lines.append(f"| {strategy} | {total} | {successful} | {rate:.1%} |")
    
    # Detailed traces
    lines.append("\n## Detailed Traces")
    
    for i, trace_dict in enumerate(report['traces'], 1):
        lines.append(f"\n### Trace {i}: {trace_dict['strategy_name']}")
        lines.append(f"- **Duration**: {trace_dict['duration_ms']:.2f}ms")
        
        if trace_dict['result']:
            result = trace_dict['result']
            lines.append(f"- **Valid**: {'✓' if result['valid'] else '✗'}")
            
            if result['error']:
                lines.append(f"- **Error**: {result['error']}")
            
            if result['suggestions']:
                lines.append("- **Suggestions**:")
                for suggestion in result['suggestions']:
                    lines.append(f"  - {suggestion}")
    
    return "\n".join(lines)


def merge_configs(*configs: Dict[str, Any]) -> Dict[str, Any]:
    """Merge multiple configuration dictionaries.
    
    Later configs override earlier ones.
    
    Args:
        *configs: Configuration dictionaries to merge
        
    Returns:
        Merged configuration
    """
    result = {}
    
    for config in configs:
        _deep_merge(result, config)
    
    return result


def _deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> None:
    """Deep merge update into base dictionary."""
    for key, value in update.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def validate_config(config: Dict[str, Any], schema: Dict[str, Any]) -> Optional[List[str]]:
    """Validate configuration against a schema.
    
    Args:
        config: Configuration to validate
        schema: Schema to validate against
        
    Returns:
        List of validation errors, or None if valid
    """
    errors = []
    
    # Check required fields
    for field, field_schema in schema.get("required", {}).items():
        if field not in config:
            errors.append(f"Missing required field: {field}")
        else:
            # Type check
            expected_type = field_schema.get("type")
            actual_type = type(config[field]).__name__
            
            if expected_type and actual_type != expected_type:
                errors.append(
                    f"Field '{field}' has wrong type: expected {expected_type}, got {actual_type}"
                )
    
    # Check optional fields
    for field, field_schema in schema.get("optional", {}).items():
        if field in config:
            expected_type = field_schema.get("type")
            actual_type = type(config[field]).__name__
            
            if expected_type and actual_type != expected_type:
                errors.append(
                    f"Field '{field}' has wrong type: expected {expected_type}, got {actual_type}"
                )
    
    return errors if errors else None


# Configuration schema
CONFIG_SCHEMA = {
    "required": {
        "model": {"type": "str", "description": "LLM model to use"},
    },
    "optional": {
        "enable_validation": {"type": "bool", "description": "Enable validation loop"},
        "validation_strategies": {"type": "list", "description": "List of validation strategies"},
        "max_retries": {"type": "int", "description": "Maximum retry attempts"},
        "debug_mode": {"type": "bool", "description": "Enable debug mode"},
        "cache_enabled": {"type": "bool", "description": "Enable caching"},
    }
}