"""Preset matching for Stage-00 profile detection.

Matches a PDF's analysis results against the preset registry to find
the best configuration preset (e.g. arxiv, requirements_spec, etc.).

Inputs: Analysis dict, filename, detected domain
Outputs: Dict with matched preset, confidence, scores, match_details
Failure: Returns needs_new_preset=True if no preset matches
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from extractor.core.presets import PRESET_REGISTRY


def match_preset(
    analysis: Dict,
    filename: str,
    detected_domain: Optional[str] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Match PDF against preset registry."""
    text = analysis.get("full_text_sample", "")
    text_lower = text.lower()

    best_score = 0
    best_preset = None
    scores: dict[str, int] = {}
    match_details = {} if verbose else None

    for name, config in PRESET_REGISTRY.items():
        detection = config.get("detection", {})
        if not detection:
            continue

        score = 0
        details = {
            "keyword_matches": [], "filename_triggers": [],
            "layout_match": None, "section_pattern_match": False,
            "domain_boost": False,
        } if verbose else None

        for kw in detection.get("keywords", []):
            if kw.lower() in text_lower:
                score += 1
                if verbose:
                    idx = text_lower.find(kw.lower())
                    context = text[max(0, idx - 20):idx + len(kw) + 20] if idx >= 0 else ""
                    details["keyword_matches"].append({"keyword": kw, "context": context[:50]})

        preset_layout = detection.get("layout")
        has_multi = analysis.get("has_multi_column")
        if preset_layout == "double" and has_multi:
            score += 3
            if verbose:
                details["layout_match"] = "double-column matched (+3)"
        elif preset_layout == "single" and not has_multi:
            score += 2
            if verbose:
                details["layout_match"] = "single-column matched (+2)"
        elif verbose:
            details["layout_match"] = (
                f"mismatch: preset={preset_layout}, "
                f"doc={'multi' if has_multi else 'single'}"
            )

        pat = detection.get("section_pattern")
        if pat and re.search(pat, text, re.MULTILINE):
            score += 4
            if verbose:
                details["section_pattern_match"] = True

        filename_lower = filename.lower()
        for t in detection.get("filename_triggers", []):
            if t in filename_lower:
                score += 5
                if verbose:
                    details["filename_triggers"].append(t)

        if detected_domain and config.get("category", "").lower() == detected_domain.lower():
            score += 5
            if verbose:
                details["domain_boost"] = True

        scores[name] = score
        if verbose:
            details["final_score"] = score
            details["min_score_required"] = detection.get("min_score", 1)
            match_details[name] = details

        if score >= detection.get("min_score", 1) and score > best_score:
            best_score = score
            best_preset = name

    result: Dict[str, Any] = {
        "matched": best_preset,
        "confidence": best_score,
        "all_scores": scores,
        "needs_new_preset": best_preset is None,
        "errors": PRESET_REGISTRY[best_preset].get("errors", []) if best_preset else [],
        "features": PRESET_REGISTRY[best_preset].get("features", {}) if best_preset else {},
    }

    if verbose:
        result["match_details"] = match_details
        if best_preset:
            d = match_details[best_preset]
            reasons = []
            if d["keyword_matches"]:
                reasons.append(f"{len(d['keyword_matches'])} keyword(s) matched")
            if d["filename_triggers"]:
                reasons.append(f"filename trigger '{d['filename_triggers'][0]}' matched (+5)")
            if d["layout_match"] and "matched" in d["layout_match"]:
                reasons.append(d["layout_match"])
            if d["section_pattern_match"]:
                reasons.append("section pattern matched (+4)")
            if d["domain_boost"]:
                reasons.append("domain category matched (+5)")
            result["selection_reason"] = "; ".join(reasons) if reasons else "default selection"
        else:
            result["selection_reason"] = "No preset met minimum score threshold"

    return result
