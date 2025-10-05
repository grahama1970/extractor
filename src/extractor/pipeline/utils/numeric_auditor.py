#!/usr/bin/env python3
"""
Numeric Integrity Auditor (Scaffold)
====================================

Extracts numeric literals from text before/after reflow to measure precision and recall.
This is scaffolding for future Stage 07 integration.

Purpose:
- Detect numeric content loss during reflow/transformation
- Provide recall (% of original numerics preserved) and precision (% of output numerics valid)
- Sample missing/extra numerics for diagnostic analysis

Future Integration:
    In Stage 07 (reflow_section.py), after generating reflowed text:
    
    from extractor.pipeline.utils.numeric_auditor import audit_section_reflow
    
    audit = audit_section_reflow(
        original_text=section["content"],
        reflow_text=reflowed_output
    )
    
    section["metadata"]["numeric_audit"] = audit
    # Use audit["recall"] and audit["precision"] in confidence composition

Current Status:
    - Module implemented and tested
    - NOT yet invoked in Stage 07
    - To be integrated in separate PR after Stage 04/05 changes

Example:
    >>> audit = audit_section_reflow(
    ...     original_text="The voltage is 3.3V and current is 2.5A. Max temp: 125°C.",
    ...     reflow_text="Voltage: 3.3V, Current: 2.5A. Maximum temperature: 125C."
    ... )
    >>> audit
    {
        "original_count": 4,
        "reflow_count": 4,
        "matched_count": 4,
        "recall": 1.0,
        "precision": 1.0,
        "missing_samples": [],
        "extra_samples": [],
        "confidence_factor": 1.0
    }
"""

from typing import Dict, Any, List, Set
import re


def extract_numeric_literals(text: str, max_samples: int = 10) -> List[str]:
    """
    Extract numeric literals from text, including decimals, units, and scientific notation.
    
    Patterns matched:
    - Integers: 42, 1000
    - Decimals: 3.14, 0.5
    - With units: 3.3V, 2.5A, 125°C, 100MHz
    - Scientific: 1.5e-6, 2.3E+10
    - Negative: -10, -3.5
    
    Args:
        text: Input text to scan
        max_samples: Maximum samples to return (for diagnostics)
        
    Returns:
        List of numeric literal strings found
    """
    if not text:
        return []
    
    # Comprehensive numeric pattern
    # Matches: optional sign, digits, optional decimal, optional exponent, optional unit
    pattern = r'-?\d+\.?\d*(?:[eE][+-]?\d+)?[A-Za-z°µ]*'
    
    matches = re.findall(pattern, text)
    
    # Filter out non-numeric matches (e.g., standalone letters)
    numeric_matches = []
    for match in matches:
        # Must start with digit or negative sign followed by digit
        if re.match(r'-?\d', match):
            numeric_matches.append(match)
    
    return numeric_matches[:max_samples] if max_samples else numeric_matches


def audit_section_reflow(
    original_text: str,
    reflow_text: str,
    max_samples: int = 5,
) -> Dict[str, Any]:
    """
    Audit numeric content preservation during section reflow.
    
    Computes:
    - recall: % of original numerics found in reflow
    - precision: % of reflow numerics that existed in original
    - confidence_factor: Geometric mean of recall and precision
    
    Args:
        original_text: Original section text before reflow
        reflow_text: Reflowed/enhanced text after processing
        max_samples: Max missing/extra samples to include
        
    Returns:
        Dictionary with audit results:
        - original_count: Number of numerics in original
        - reflow_count: Number of numerics in reflow
        - matched_count: Number of numerics present in both
        - recall: Fraction of original numerics preserved (0-1)
        - precision: Fraction of reflow numerics valid (0-1)
        - confidence_factor: Geometric mean of recall and precision (0-1)
        - missing_samples: Examples of numerics lost
        - extra_samples: Examples of numerics added
    """
    # Extract all numeric literals
    original_nums = extract_numeric_literals(original_text, max_samples=None)
    reflow_nums = extract_numeric_literals(reflow_text, max_samples=None)
    
    # Use sets for matching (case-insensitive, normalized)
    original_set = set(n.lower() for n in original_nums)
    reflow_set = set(n.lower() for n in reflow_nums)
    
    # Count matches
    matched = original_set & reflow_set
    matched_count = len(matched)
    
    # Compute metrics
    original_count = len(original_set)
    reflow_count = len(reflow_set)
    
    recall = matched_count / original_count if original_count > 0 else 1.0
    precision = matched_count / reflow_count if reflow_count > 0 else 1.0
    
    # Confidence factor: geometric mean of recall and precision
    # If either is 0, factor is 0; otherwise sqrt(recall * precision)
    if recall > 0 and precision > 0:
        confidence_factor = (recall * precision) ** 0.5
    else:
        confidence_factor = 0.0
    
    # Collect samples of missing and extra numerics
    missing = original_set - reflow_set
    extra = reflow_set - original_set
    
    missing_samples = sorted(list(missing))[:max_samples]
    extra_samples = sorted(list(extra))[:max_samples]
    
    return {
        "original_count": original_count,
        "reflow_count": reflow_count,
        "matched_count": matched_count,
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "confidence_factor": round(confidence_factor, 4),
        "missing_samples": missing_samples,
        "extra_samples": extra_samples,
    }


def format_audit_report(audit: Dict[str, Any]) -> str:
    """
    Format audit result as human-readable text.
    
    Args:
        audit: Result from audit_section_reflow()
        
    Returns:
        Multi-line formatted report string
    """
    lines = [
        "Numeric Content Audit:",
        f"  Original numerics: {audit['original_count']}",
        f"  Reflow numerics: {audit['reflow_count']}",
        f"  Matched: {audit['matched_count']}",
        f"  Recall: {audit['recall']:.2%}",
        f"  Precision: {audit['precision']:.2%}",
        f"  Confidence: {audit['confidence_factor']:.4f}",
    ]
    
    if audit["missing_samples"]:
        lines.append(f"\n  Missing numerics ({len(audit['missing_samples'])}):")
        for num in audit["missing_samples"]:
            lines.append(f"    - {num}")
    
    if audit["extra_samples"]:
        lines.append(f"\n  Extra numerics ({len(audit['extra_samples'])}):")
        for num in audit["extra_samples"]:
            lines.append(f"    - {num}")
    
    return "\n".join(lines)
