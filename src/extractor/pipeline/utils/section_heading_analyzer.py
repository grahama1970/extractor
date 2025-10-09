#!/usr/bin/env python3
"""
section_heading_analyzer.py

Analyzes section headings for anomalies and produces a per-section
confidence factor used as a multiplicative component.
"""

from __future__ import annotations
from typing import List, Dict, Any
import statistics


def analyze_sections(sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {"sections": {}, "global": {}}
    if not sections:
        return result

    ordered = []
    for s in sections:
        title = (s.get("title") or "").strip()
        level = int(s.get("level") or 1)
        ordered.append((s.get("id"), title, level))

    # Frequency analysis
    freq = {}
    for _, t, _ in ordered:
        if t:
            freq[t] = freq.get(t, 0) + 1
    repeated_wrappers = [t for t, c in freq.items() if c > 3 and _is_wrapper_like(t)]
    result["global"]["repeated_wrappers"] = repeated_wrappers

    # Level jump stats
    jumps = []
    prev_level = ordered[0][2]
    for _, _, lvl in ordered[1:]:
        jumps.append(lvl - prev_level)
        prev_level = lvl
    if jumps:
        result["global"]["level_jump_stats"] = {
            "mean": statistics.mean(jumps),
            "stdev": statistics.pstdev(jumps),
            "max_abs": max(abs(j) for j in jumps),
        }

    prev_level = ordered[0][2]
    for sid, title, lvl in ordered:
        anomalies = []
        if lvl - prev_level > 2:
            anomalies.append("level_jump_up")
        if prev_level - lvl > 2:
            anomalies.append("level_jump_down")
        if title in repeated_wrappers:
            anomalies.append("repeated_wrapper")
        if len(title) <= 40 and title.endswith(":"):
            anomalies.append("short_colon_heading")
        if title and title.isupper() and 1 < len(title) < 8:
            anomalies.append("acronym_heading")
        prev_level = lvl
        factor = _confidence_factor(anomalies)
        result["sections"][sid] = {"anomalies": anomalies, "confidence_factor": factor}

    return result


def _is_wrapper_like(title: str) -> bool:
    low = title.lower()
    patterns = [
        "introduction",
        "summary",
        "overview",
        "appendix",
        "annex",
        "table of contents",
    ]
    return any(p in low for p in patterns)


def _confidence_factor(anomalies) -> float:
    factor = 1.0
    for a in anomalies:
        if a in ("level_jump_up", "level_jump_down"):
            factor -= 0.12
        elif a == "repeated_wrapper":
            factor -= 0.08
        elif a == "short_colon_heading":
            factor -= 0.05
    return max(0.4, round(factor, 3))

