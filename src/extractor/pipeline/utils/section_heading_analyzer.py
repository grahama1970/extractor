#!/usr/bin/env python3
"""
Section Heading Anomaly Analyzer
=================================

Detects structural anomalies in section hierarchies to improve confidence scoring.

Detected Anomalies:
1. Level jumps: Skipping hierarchy levels (e.g., 1 -> 3)
2. Repeated wrapper headings: Generic container headings like "REQUIREMENTS (Simulated)"
3. Colon-short headings: Suspiciously short headings ending with colon (likely labels)

Returns:
- List of detected anomalies with type, location, and severity
- confidence_factor: Multiplicative factor (0-1) based on anomaly severity
  * 1.0 = clean hierarchy, no issues
  * 0.95 = minor issues (1-2 level jumps)
  * 0.85 = moderate issues (wrapper headings detected)
  * 0.70 = significant issues (multiple anomalies)

Usage:
    from extractor.pipeline.utils.section_heading_analyzer import analyze_section_headings
    
    sections = [
        {"id": "s1", "title": "Introduction", "level": 1},
        {"id": "s2", "title": "Background:", "level": 1},  # Short colon
        {"id": "s3", "title": "Methods", "level": 3},  # Level jump (1->3)
    ]
    
    result = analyze_section_headings(sections)
    # {
    #   "anomalies": [
    #     {"type": "colon_short", "section_id": "s2", "title": "Background:", ...},
    #     {"type": "level_jump", "section_id": "s3", "from_level": 1, "to_level": 3, ...}
    #   ],
    #   "confidence_factor": 0.85,
    #   "total_sections": 3,
    #   "anomaly_count": 2
    # }
"""

from typing import Dict, Any, List, Optional
import re


def analyze_section_headings(
    sections: List[Dict[str, Any]],
    max_colon_length: int = 40,
    wrapper_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Analyze section headings for structural anomalies.
    
    Args:
        sections: List of section dicts with "id", "title", "level" keys
        max_colon_length: Max length for colon-ending heading to be suspicious
        wrapper_patterns: Regex patterns for wrapper headings (defaults provided)
        
    Returns:
        Dictionary containing:
        - anomalies: List of detected anomaly dicts
        - confidence_factor: Multiplicative confidence adjustment (0-1)
        - total_sections: Number of sections analyzed
        - anomaly_count: Total number of anomalies detected
        - severity_breakdown: Count by severity level
    """
    if not sections:
        return {
            "anomalies": [],
            "confidence_factor": 1.0,
            "total_sections": 0,
            "anomaly_count": 0,
            "severity_breakdown": {},
        }
    
    # Default wrapper patterns (case-insensitive)
    if wrapper_patterns is None:
        wrapper_patterns = [
            r"requirements\s*\(simulated\)",
            r"^\s*[\w\s]+ - continued\s*$",
            r"^(table of contents|appendix|references)\s*:?\s*$",
        ]
    
    anomalies: List[Dict[str, Any]] = []
    
    # Track previous level for jump detection
    prev_level: Optional[int] = None
    prev_section_id: Optional[str] = None
    
    for section in sections:
        section_id = section.get("id", "unknown")
        title = section.get("title", "").strip()
        level = section.get("level")
        
        if not isinstance(level, int):
            continue
        
        # 1. Detect level jumps (skipping levels)
        if prev_level is not None and level > prev_level + 1:
            anomalies.append({
                "type": "level_jump",
                "severity": "moderate",
                "section_id": section_id,
                "title": title,
                "from_level": prev_level,
                "to_level": level,
                "previous_section_id": prev_section_id,
                "message": f"Level jumped from {prev_level} to {level} (skipped {level - prev_level - 1} level(s))",
            })
        
        # 2. Detect wrapper headings
        title_lower = title.lower()
        for pattern in wrapper_patterns:
            if re.search(pattern, title_lower):
                anomalies.append({
                    "type": "wrapper_heading",
                    "severity": "minor",
                    "section_id": section_id,
                    "title": title,
                    "level": level,
                    "pattern": pattern,
                    "message": f"Wrapper heading detected: '{title}'",
                })
                break  # Only report once per section
        
        # 3. Detect short colon-ending headings (likely labels, not headings)
        if len(title) <= max_colon_length and title.endswith(":"):
            anomalies.append({
                "type": "colon_short",
                "severity": "minor",
                "section_id": section_id,
                "title": title,
                "level": level,
                "length": len(title),
                "message": f"Short colon-ending heading: '{title}' ({len(title)} chars)",
            })
        
        prev_level = level
        prev_section_id = section_id
    
    # Compute confidence factor based on anomaly severity
    confidence_factor = _compute_confidence_factor(anomalies)
    
    # Breakdown by severity
    severity_counts = {}
    for anomaly in anomalies:
        severity = anomaly.get("severity", "unknown")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
    
    return {
        "anomalies": anomalies,
        "confidence_factor": confidence_factor,
        "total_sections": len(sections),
        "anomaly_count": len(anomalies),
        "severity_breakdown": severity_counts,
    }


def _compute_confidence_factor(anomalies: List[Dict[str, Any]]) -> float:
    """
    Compute confidence factor from anomaly list.
    
    Severity penalties:
    - minor: -0.02 per anomaly
    - moderate: -0.05 per anomaly
    - major: -0.10 per anomaly
    
    Floor: 0.50 (never go below 50% confidence due to heading issues alone)
    
    Args:
        anomalies: List of anomaly dicts with "severity" key
        
    Returns:
        Confidence factor between 0.5 and 1.0
    """
    if not anomalies:
        return 1.0
    
    severity_penalties = {
        "minor": 0.02,
        "moderate": 0.05,
        "major": 0.10,
    }
    
    penalty = 0.0
    for anomaly in anomalies:
        severity = anomaly.get("severity", "minor")
        penalty += severity_penalties.get(severity, 0.02)
    
    # Apply penalty with floor
    factor = max(0.50, 1.0 - penalty)
    return round(factor, 4)


def format_anomaly_report(analysis: Dict[str, Any]) -> str:
    """
    Format anomaly analysis as human-readable text.
    
    Args:
        analysis: Result from analyze_section_headings()
        
    Returns:
        Multi-line formatted report string
    """
    lines = [
        f"Section Heading Analysis:",
        f"  Total sections: {analysis['total_sections']}",
        f"  Anomalies found: {analysis['anomaly_count']}",
        f"  Confidence factor: {analysis['confidence_factor']:.4f}",
    ]
    
    if analysis["severity_breakdown"]:
        lines.append("  Severity breakdown:")
        for severity, count in analysis["severity_breakdown"].items():
            lines.append(f"    {severity}: {count}")
    
    if analysis["anomalies"]:
        lines.append("\nDetailed Anomalies:")
        for i, anomaly in enumerate(analysis["anomalies"], 1):
            lines.append(f"  {i}. [{anomaly['type']}] {anomaly['message']}")
            lines.append(f"     Section: {anomaly['section_id']}")
    
    return "\n".join(lines)
