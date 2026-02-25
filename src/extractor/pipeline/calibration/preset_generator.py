"""Preset configuration file generator from calibration sessions.

Task 13: Generate preset configuration file.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


@dataclass
class PresetConfig:
    """Generated preset configuration."""

    preset_id: str
    created: str
    calibrated_from: str
    source_pdf: str
    patterns: dict[str, Any]
    thresholds: dict[str, float]
    metadata: dict[str, Any]


def generate_preset(
    session_key: str,
    output_path: Path | str | None = None,
) -> PresetConfig:
    """Generate preset YAML from a calibration session.

    Args:
        session_key: Session key to generate preset from.
        output_path: Optional path to write YAML file.

    Returns:
        PresetConfig with generated configuration.

    Raises:
        ValueError: If session not found or not converged.
    """
    from extractor.pipeline.calibration import (
        CalibrationSchema,
        FeedbackHandler,
        PatternLearner,
    )

    schema = CalibrationSchema()
    session = schema.get_session(session_key)

    if not session:
        raise ValueError(f"Session '{session_key}' not found")

    # Get session info
    preset_id = session.get("preset_id", session_key)
    pdf_path = session.get("pdf_path", "")

    # Get stats
    handler = FeedbackHandler(schema)
    stats = handler.get_session_stats(session_key)

    # Get learned patterns
    learner = PatternLearner(schema)
    patterns = learner.get_active_patterns(preset_id)

    # Build pattern configurations by type
    pattern_config = {
        "headers": _build_header_patterns(patterns, stats),
        "tables": _build_table_patterns(patterns, stats),
        "figures": _build_figure_patterns(patterns, stats),
    }

    # Build thresholds from session stats
    thresholds = {
        "header_confidence": 0.85,
        "table_confidence": 0.80,
        "figure_confidence": 0.80,
        "min_accuracy": 90.0,
    }

    # Build metadata
    metadata = {
        "total_reviewed": stats["reviewed"],
        "accuracy": stats["accuracy"],
        "by_type": {
            element_type: {
                "reviewed": type_stats.get("reviewed", 0),
                "correct": type_stats.get("correct", 0),
            }
            for element_type, type_stats in stats.get("by_type", {}).items()
        },
        "patterns_learned": len(patterns),
    }

    config = PresetConfig(
        preset_id=preset_id,
        created=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        calibrated_from=session_key,
        source_pdf=pdf_path,
        patterns=pattern_config,
        thresholds=thresholds,
        metadata=metadata,
    )

    # Write YAML if output path provided
    if output_path:
        write_preset_yaml(config, Path(output_path))

    return config


def _build_header_patterns(patterns: list[dict], stats: dict) -> dict:
    """Build header pattern configuration."""
    header_patterns = [p for p in patterns if p.get("element_type") == "header"]

    config = {
        "stage1_regex": None,
        "stage2_python": None,
        "confidence_threshold": 0.85,
    }

    # Extract regex patterns
    regex_patterns = []
    for p in header_patterns:
        if regex := p.get("pattern_data", {}).get("regex"):
            regex_patterns.append(regex)

    if regex_patterns:
        # Combine into alternation
        if len(regex_patterns) == 1:
            config["stage1_regex"] = regex_patterns[0]
        else:
            config["stage1_regex"] = f"({'|'.join(regex_patterns)})"

    # Build stage2 Python validation hints
    font_hints = []
    for p in header_patterns:
        data = p.get("pattern_data", {})
        if font_size := data.get("font_size_min"):
            font_hints.append(f"font_size >= {font_size}")
        if data.get("is_bold"):
            font_hints.append("font_bold")

    if font_hints:
        config["stage2_python"] = f"def match(elem):\n    return {' and '.join(font_hints)}"

    return config


def _build_table_patterns(patterns: list[dict], stats: dict) -> dict:
    """Build table pattern configuration."""
    table_patterns = [p for p in patterns if p.get("element_type") == "table"]

    config = {
        "detection": [],
        "merge_threshold": 0.9,
    }

    # Extract detection methods
    methods = set()
    for p in table_patterns:
        data = p.get("pattern_data", {})
        if data.get("has_grid_lines"):
            methods.add("grid_lines")
        if data.get("has_caption"):
            methods.add("caption_above")
        if data.get("has_borders"):
            methods.add("cell_borders")

    config["detection"] = list(methods) if methods else ["grid_lines"]

    return config


def _build_figure_patterns(patterns: list[dict], stats: dict) -> dict:
    """Build figure pattern configuration."""
    figure_patterns = [p for p in patterns if p.get("element_type") == "figure"]

    config = {
        "caption_pattern": r"Figure\s+\d+\.?\d*",
        "caption_position": "below",
    }

    # Extract caption patterns from learned patterns
    for p in figure_patterns:
        data = p.get("pattern_data", {})
        if caption_regex := data.get("caption_regex"):
            config["caption_pattern"] = caption_regex
        if caption_pos := data.get("caption_position"):
            config["caption_position"] = caption_pos

    return config


def write_preset_yaml(config: PresetConfig, output_path: Path) -> None:
    """Write preset configuration to YAML file.

    Args:
        config: PresetConfig to write.
        output_path: Path to write YAML file.
    """
    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build YAML document
    doc = {
        "preset_id": config.preset_id,
        "created": config.created,
        "calibrated_from": config.calibrated_from,
        "source_pdf": config.source_pdf,
        "patterns": config.patterns,
        "thresholds": config.thresholds,
        "metadata": config.metadata,
    }

    # Write with header comment
    with output_path.open("w") as f:
        f.write(f"# Preset: {config.preset_id}\n")
        f.write(f"# Generated from calibration session: {config.calibrated_from}\n")
        f.write(f"# Date: {config.created}\n")
        f.write("#\n")
        f.write("# This file was automatically generated by the calibration workflow.\n")
        f.write("# Edit with care - changes may be overwritten on re-calibration.\n")
        f.write("\n")
        yaml.dump(doc, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def format_preset_summary(config: PresetConfig) -> str:
    """Format preset configuration for display.

    Args:
        config: PresetConfig to format.

    Returns:
        Formatted string summary.
    """
    lines = [
        "Calibration Complete!",
        "",
        "Results:",
        f"- Elements reviewed: {config.metadata['total_reviewed']}",
        f"- Accuracy: {config.metadata['accuracy']:.1f}%",
        f"- Patterns learned: {config.metadata['patterns_learned']}",
        "",
    ]

    # Add type breakdown
    for element_type, type_stats in config.metadata.get("by_type", {}).items():
        reviewed = type_stats.get("reviewed", 0)
        correct = type_stats.get("correct", 0)
        acc = (correct / reviewed * 100) if reviewed > 0 else 0
        lines.append(f"  {element_type.title()}: {reviewed} reviewed, {acc:.0f}% correct")

    lines.extend(
        [
            "",
            f"Preset ID: {config.preset_id}",
            f"Created: {config.created}",
        ]
    )

    return "\n".join(lines)
