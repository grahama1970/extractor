"""
Glossary Entry Extractor — /assistant wrapper for term→definition extraction.

Calls the `glossary-entry-extractor` task through the /assistant 4-tier cascade:
  Tier 0:   Heuristic (structural line-level detection)
  Tier 0.5: Classifier (trained via /classifier-lab, when available)
  Tier 1.5: Local GPT (trained via /assistant-lab, when available)
  Tier 2:   scillm teacher (DeepSeek V3.2)

Also provides content verification: given section text, confirm it contains
≥N term→definition pairs (used by S04 to validate glossary section detection).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from loguru import logger


# ---------------------------------------------------------------------------
# Tier 0 heuristic: structural line-level entry detection
# ---------------------------------------------------------------------------

# Patterns that match common glossary formats:
#   TERM - Definition text
#   TERM: Definition text
#   TERM\tDefinition text
#   TERM   Definition text (3+ spaces)
_ENTRY_PATTERN = re.compile(
    r"^(?P<term>[A-Z][A-Za-z0-9/&.\-]{0,50})"  # Term: starts uppercase, short
    r"\s*"
    r"(?:[-–—:]\s+|\t+|\s{3,})"  # Separator: dash, colon, tab, or wide gap
    r"(?P<definition>.{10,})"  # Definition: at least 10 chars
    r"$",
    re.MULTILINE,
)


def _heuristic_extract(text: str) -> List[Dict[str, str]]:
    """Tier 0: Extract entries via structural regex. Fast path for obvious formats."""
    entries = []
    seen = set()
    for m in _ENTRY_PATTERN.finditer(text):
        term = m.group("term").strip()
        definition = m.group("definition").strip()
        key = term.lower()
        if key not in seen:
            seen.add(key)
            # Guess category from term shape
            category = "acronym" if term.isupper() and len(term) <= 10 else "definition"
            entries.append({
                "term": term,
                "definition": definition,
                "category": category,
            })
    return entries


# ---------------------------------------------------------------------------
# /assistant integration
# ---------------------------------------------------------------------------

def _assistant_available() -> bool:
    """Check if the /assistant Python API is importable."""
    try:
        from assistant import validate  # noqa: F401
        return True
    except ImportError:
        return False


def _assistant_extract(text: str) -> List[Dict[str, str]]:
    """Call /assistant glossary-entry-extractor task via the 4-tier cascade."""
    try:
        from assistant import validate

        result = validate(
            input_data={"text": text},
            task="glossary-entry-extractor",
            scope="extractor",
        )
        if result and result.result:
            entries = result.result if isinstance(result.result, list) else result.result.get("entries", [])
            logger.debug(
                f"glossary-entry-extractor returned {len(entries)} entries "
                f"(tier={result.tier}, confidence={result.confidence:.2f})"
            )
            return [
                {
                    "term": e.get("term", ""),
                    "definition": e.get("definition", ""),
                    "category": e.get("category", "definition"),
                }
                for e in entries
                if e.get("term") and e.get("definition")
            ]
    except Exception as e:
        logger.warning(f"glossary-entry-extractor failed: {e}")
    return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_glossary_entries(text: str) -> List[Dict[str, str]]:
    """
    Extract term→definition pairs from glossary section text.

    Tries heuristic first; if <3 entries and /assistant is available,
    escalates to the /assistant cascade for better coverage.

    Returns list of {"term", "definition", "category"}.
    """
    if not text or not text.strip():
        return []

    # Tier 0: heuristic
    entries = _heuristic_extract(text)
    if len(entries) >= 3:
        logger.debug(f"Heuristic extracted {len(entries)} glossary entries")
        return entries

    # Escalate to /assistant if available
    if _assistant_available():
        assistant_entries = _assistant_extract(text)
        if len(assistant_entries) > len(entries):
            return assistant_entries

    return entries


def verify_glossary_content(text: str, min_pairs: int = 3) -> bool:
    """
    Verify that section text contains actual glossary entries.

    Used by S04 to confirm a candidate glossary section after title-based detection.
    Returns True if ≥min_pairs term→definition pairs are found.
    """
    entries = extract_glossary_entries(text)
    return len(entries) >= min_pairs


# ---------------------------------------------------------------------------
# Shared glossary constants (imported by s04_section_builder, collect_training_data)
# ---------------------------------------------------------------------------

GLOSSARY_KEYWORDS = frozenset({
    "acronyms", "definitions", "glossary", "abbreviations",
    "terminology", "terms and definitions", "acronyms and definitions",
    "acronyms and abbreviations", "list of acronyms", "list of abbreviations",
    "list of terms", "nomenclature", "symbols and abbreviations",
})

GLOSSARY_WORDS = frozenset({
    "acronym", "abbreviation", "glossary", "definition",
    "nomenclature", "terminology", "symbol",
})


# ---------------------------------------------------------------------------
# Glossary section classifier (ML model, optional)
# ---------------------------------------------------------------------------

_CLASSIFIER_ARTIFACT = None
_CLASSIFIER_CHECKED = False
_MODEL_PATH = "models/glossary-section-classifier/model.joblib"


def _title_to_features(title: str) -> dict:
    """Compute tabular features from a section title."""
    lower = title.lower()
    words = title.split()
    return {
        "has_acronym_word": int(any(w in lower for w in GLOSSARY_WORDS)),
        "has_list_prefix": int(lower.startswith("list of")),
        "is_all_caps": int(title == title.upper() and len(title) > 1),
        "word_count": len(words),
    }


def _glossary_classifier_available() -> bool:
    """Check if trained glossary section classifier model exists."""
    global _CLASSIFIER_CHECKED, _CLASSIFIER_ARTIFACT
    if _CLASSIFIER_CHECKED:
        return _CLASSIFIER_ARTIFACT is not None
    _CLASSIFIER_CHECKED = True
    try:
        import joblib
        from pathlib import Path
        model_path = Path(_MODEL_PATH)
        if model_path.exists():
            _CLASSIFIER_ARTIFACT = joblib.load(model_path)
            logger.info(f"Loaded glossary section classifier from {model_path}")
            return True
    except Exception as e:
        logger.debug(f"Glossary classifier not available: {e}")
    return False


def glossary_classifier_predict(title: str) -> float:
    """
    Predict P(glossary) for a section title using the trained ML classifier.

    Returns probability 0.0-1.0. Returns 0.0 if classifier not available.
    """
    if not _glossary_classifier_available() or _CLASSIFIER_ARTIFACT is None:
        return 0.0
    try:
        import numpy as np
        model = _CLASSIFIER_ARTIFACT["model"]
        feature_keys = _CLASSIFIER_ARTIFACT["feature_keys"]
        classes = list(_CLASSIFIER_ARTIFACT["classes"])
        features = _title_to_features(title)
        x = np.array([[float(features.get(k, 0)) for k in feature_keys]])
        proba = model.predict_proba(x)
        glossary_idx = classes.index("glossary") if "glossary" in classes else 1
        return float(proba[0][glossary_idx])
    except Exception as e:
        logger.debug(f"Classifier prediction failed: {e}")
        return 0.0
