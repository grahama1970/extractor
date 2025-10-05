#!/usr/bin/env python3
"""
numeric_auditor.py

Audits numeric literal integrity between original text & reflowed text.

Returns recall, precision, counts, and sample missing/extra numbers.
"""

from __future__ import annotations
import re
from typing import List, Dict

_NUM_RE = re.compile(r"[+-]?(?:\d+\.\d+|\d+)")


def extract_numbers(text: str) -> List[str]:
    return [m.group(0) for m in _NUM_RE.finditer(text or "")]


def audit_section_reflow(original_text: str, reflow_text: str) -> Dict[str, object]:
    orig = extract_numbers(original_text)
    new = extract_numbers(reflow_text)

    orig_m = {}
    new_m = {}
    for n in orig:
        orig_m[n] = orig_m.get(n, 0) + 1
    for n in new:
        new_m[n] = new_m.get(n, 0) + 1

    intersection = 0
    for k, v in orig_m.items():
        if k in new_m:
            intersection += min(v, new_m[k])

    recall = intersection / len(orig) if orig else None
    precision = intersection / len(new) if new else None

    missing = []
    for k, v in orig_m.items():
        diff = v - new_m.get(k, 0)
        if diff > 0:
            missing.extend([k] * diff)
    extra = []
    for k, v in new_m.items():
        diff = v - orig_m.get(k, 0)
        if diff > 0:
            extra.extend([k] * diff)

    return {
        "original_numeric_count": len(orig),
        "reflow_numeric_count": len(new),
        "intersection_count": intersection,
        "recall": round(recall, 4) if recall is not None else None,
        "precision": round(precision, 4) if precision is not None else None,
        "missing_samples": missing[:5],
        "extra_samples": extra[:5],
    }

