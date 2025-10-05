#!/usr/bin/env python3
"""
Confidence Composition Utilities
=================================

Composes unified confidence objects from multiple signals for accuracy tracking.
Uses geometric mean style aggregation to handle None values gracefully.

Components:
- structure_prob: Learned calibrator output (optional, 0-1)
- heading_factor: Section heading quality factor (0-1)
- numeric_recall: Numeric content preservation (0-1, future)
- hallucination_factor: Anti-hallucination score (0-1, future)

Usage:
    conf = compose_confidence(
        structure_prob=0.85,
        heading_factor=0.92,
        numeric_recall=None,  # Not yet computed
        hallucination_factor=None
    )
    # Returns: {"components": {...}, "score": 0.884, "count": 2}
"""

from typing import Dict, Any, Optional, List
import math


def compose_confidence(
    structure_prob: Optional[float] = None,
    heading_factor: Optional[float] = None,
    numeric_recall: Optional[float] = None,
    hallucination_factor: Optional[float] = None,
    **extra_components: Optional[float],
) -> Dict[str, Any]:
    """
    Compose a unified confidence object from multiple signals.
    
    Uses geometric mean of non-None components to compute overall score.
    This approach naturally handles missing components without bias.
    
    Args:
        structure_prob: Calibrated probability from learned model (0-1)
        heading_factor: Section heading quality (0-1)
        numeric_recall: Numeric content preservation (0-1)
        hallucination_factor: Anti-hallucination score (0-1)
        **extra_components: Additional named confidence components
        
    Returns:
        Dictionary with:
        - components: Dict of all named components (including None values)
        - score: Geometric mean of non-None components, or None if all None
        - count: Number of non-None components used in score
        - method: "geometric_mean"
        
    Example:
        >>> compose_confidence(structure_prob=0.8, heading_factor=0.9)
        {
            "components": {"structure_prob": 0.8, "heading_factor": 0.9, ...},
            "score": 0.8485,
            "count": 2,
            "method": "geometric_mean"
        }
    """
    components = {
        "structure_prob": structure_prob,
        "heading_factor": heading_factor,
        "numeric_recall": numeric_recall,
        "hallucination_factor": hallucination_factor,
    }
    components.update(extra_components)
    
    # Filter non-None values for score computation
    valid_values = [v for v in components.values() if v is not None]
    
    if not valid_values:
        # All components are None
        return {
            "components": components,
            "score": None,
            "count": 0,
            "method": "geometric_mean",
        }
    
    # Geometric mean: (v1 * v2 * ... * vn)^(1/n)
    # More sensitive to low values than arithmetic mean
    product = math.prod(valid_values)
    geometric_mean = product ** (1.0 / len(valid_values))
    
    return {
        "components": components,
        "score": round(geometric_mean, 4),
        "count": len(valid_values),
        "method": "geometric_mean",
    }


def merge_confidence_components(
    base_conf: Optional[Dict[str, Any]],
    new_components: Dict[str, Optional[float]],
) -> Dict[str, Any]:
    """
    Merge new confidence components into an existing confidence object.
    
    Updates components and recomputes the overall score using geometric mean.
    
    Args:
        base_conf: Existing confidence dict (or None)
        new_components: Dict of component names to values
        
    Returns:
        Updated confidence dictionary
        
    Example:
        >>> base = compose_confidence(structure_prob=0.8)
        >>> merge_confidence_components(base, {"heading_factor": 0.9})
        {"components": {...}, "score": 0.8485, "count": 2, ...}
    """
    if base_conf is None:
        base_conf = {"components": {}, "score": None, "count": 0}
    
    # Get existing components
    components = base_conf.get("components", {}).copy()
    
    # Update with new components
    components.update(new_components)
    
    # Recompute score
    return compose_confidence(**components)


def confidence_report(conf: Optional[Dict[str, Any]]) -> str:
    """
    Generate a human-readable confidence report string.
    
    Args:
        conf: Confidence dictionary from compose_confidence
        
    Returns:
        Formatted string describing confidence components and score
        
    Example:
        >>> report = confidence_report(compose_confidence(structure_prob=0.85, heading_factor=0.92))
        >>> print(report)
        Confidence: 0.8845 (2 components)
          structure_prob: 0.85
          heading_factor: 0.92
    """
    if not conf:
        return "Confidence: None"
    
    score = conf.get("score")
    count = conf.get("count", 0)
    components = conf.get("components", {})
    
    if score is None:
        return "Confidence: None (no components)"
    
    lines = [f"Confidence: {score:.4f} ({count} component{'s' if count != 1 else ''})"]
    
    for name, value in components.items():
        if value is not None:
            lines.append(f"  {name}: {value:.4f}")
        else:
            lines.append(f"  {name}: None")
    
    return "\n".join(lines)
