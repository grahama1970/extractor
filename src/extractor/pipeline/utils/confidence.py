#!/usr/bin/env python3
"""
confidence.py

Compose a unified confidence object by combining available signals.

Result structure:
{
  "score": 0.8731,
  "components": {
     "structure_prob": 0.93,
     "heading_factor": 0.88,
     "numeric_recall": 0.95
  },
  "flags": ["repeated_wrapper"]
}
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any


def compose_confidence(
    *,
    structure_prob: Optional[float],
    heading_factor: Optional[float],
    numeric_recall: Optional[float],
    hallucination_factor: Optional[float],
    extra_flags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    components = {}
    factors = []

    if structure_prob is not None:
        components["structure_prob"] = round(structure_prob, 4)
        factors.append(_prob_to_factor(structure_prob))
    if heading_factor is not None:
        components["heading_factor"] = heading_factor
        factors.append(heading_factor)
    if numeric_recall is not None:
        components["numeric_recall"] = numeric_recall
        factors.append(max(0.5, numeric_recall))
    if hallucination_factor is not None:
        components["hallucination_factor"] = hallucination_factor
        factors.append(hallucination_factor)

    if not factors:
        score = None
    else:
        product = 1.0
        for f in factors:
            product *= f
        score = round(product ** (1 / len(factors)), 4)

    return {
        "score": score,
        "components": components,
        "flags": extra_flags or [],
    }


def _prob_to_factor(p: float) -> float:
    # Map probability in [0,1] to multiplicative factor ~[0.6,1.1]
    p = max(0.0, min(1.0, p))
    return round(0.6 + (p * 0.5), 4)

