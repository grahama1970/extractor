#!/usr/bin/env python3
"""Pandas metrics and scoring utilities for Stage 05 (Table Extractor).

Generates quality metrics and scores for extracted tables.
"""

from __future__ import annotations

from typing import Any, Dict, List

import os
import re
import pandas as pd


def generate_pandas_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """Generate comprehensive metrics from a DataFrame for analysis."""
    if df.empty:
        return {"shape": [0, 0], "error": "Empty DataFrame"}

    total_cells = df.size
    non_empty_cells = df.astype(str).ne("").sum().sum()

    metrics = {
        "shape": list(df.shape),
        "columns": [str(c) for c in df.columns],
        "dtypes": {str(k): str(v) for k, v in df.dtypes.to_dict().items()},
        "null_counts": {str(k): int(v) for k, v in df.isnull().sum().to_dict().items()},
        "total_cells": int(total_cells),
        "non_empty_cells": int(non_empty_cells),
        "data_density": float(non_empty_cells / total_cells) if total_cells > 0 else 0.0,
    }
    return metrics


def score_table(df: pd.DataFrame) -> float:
    """Score a table based on non-empty cell count."""
    if df.empty:
        return 0.0
    return float(df.astype(str).ne("").sum().sum())


def iou(a: List[float], b: List[float]) -> float:
    """Calculate Intersection over Union for two [x0, y0, x1, y1] boxes."""
    try:
        ax0, ay0, ax1, ay1 = a
        bx0, by0, bx1, by1 = b
        inter_w = max(0.0, min(ax1, bx1) - max(ax0, bx0))
        inter_h = max(0.0, min(ay1, by1) - max(ay0, by0))
        inter = inter_w * inter_h
        area_a = max(0.0, (ax1 - ax0)) * max(0.0, (ay1 - ay0))
        area_b = max(0.0, (bx1 - bx0)) * max(0.0, (by1 - by0))
        union = area_a + area_b - inter
        return float(inter / union) if union > 0 else 0.0
    except Exception:
        return 0.0


def horizontal_iou(a: List[float], b: List[float]) -> float:
    """Calculate 1D Intersection over Union on the X-axis only."""
    try:
        ax0, _, ax1, _ = a
        bx0, _, bx1, _ = b
        inter = max(0.0, min(ax1, bx1) - max(ax0, bx0))
        uni = max(ax1, bx1) - min(ax0, bx0)
        return float(inter / uni) if uni > 0 else 0.0
    except Exception:
        return 0.0


__all__ = [
    "generate_pandas_metrics",
    "score_table",
    "iou",
    "horizontal_iou",
    "normalize_cell",
    "sanitize_cell",
    "fragmentation_score",
    "fragmentation_score_with_domain",
    "should_retry_fragmentation",
    "has_fragmentation_improvement",
    "should_replace_table",
]

# Pattern: a word fragment followed by a space and exactly 2 trailing letters.
# Matches OCR-broken words like "EXECU TE", "Descripti on".
# Single-letter trailing fragments are too ambiguous (math variables like
# "variable z" vs OCR breaks like "Subsyste m") so they are handled by
# _KNOWN_LONG_BREAKS lookup instead.
# Combined with _COMMON_SHORT_WORDS stopword filter to block matches where
# the trailing fragment is a real English word ("vibration to", "Division of").
_BROKEN_WORD_RE = re.compile(r"([a-zA-Z]{3,})\s([a-zA-Z]{2})(?=\s|$)")

# Common 1-2 character English words, abbreviations, and Latin terms.
# When these appear as the trailing fragment in a regex match, they are
# almost always real words, NOT OCR fragments.
_COMMON_SHORT_WORDS = frozenset({
    # Basic English words
    "a", "i",
    "al", "am", "an", "as", "at", "be", "by", "do", "et", "go", "he",
    "id", "if", "in", "is", "it", "me", "my", "no", "of", "on", "or",
    "so", "sp", "sw", "to", "up", "us", "vs", "we",
    # Roman numerals and technical abbreviations
    "ff", "ii", "iv", "vi", "ix", "xi",
    # Programming language keywords and common abbreviations
    "fn", "ir", "cc", "ty", "ai", "ks", "vk", "wk", "hu",
    # Scientific/Latin abbreviations (common in arxiv papers)
    "eg", "ie", "cf", "op", "re", "se", "ex", "eq",
    # Math operators and functions
    "ln", "lg", "le", "ge", "ne", "pm", "mp",
    # Units (common in scientific tables)
    "ms", "ns", "us", "ps", "fs",  # time units
    "kb", "mb", "gb", "tb", "pb",  # data units
    "hz", "mw", "kw", "gw", "ev",  # power/energy
    "db", "nm", "um", "mm", "cm", "km",  # measurement
    # Greek letter abbreviations often used in papers
    "pi", "mu", "nu", "xi", "ph", "ps",
    # Common table cell values in scientific papers
    "na", "nd", "nr", "ns", "nt",  # "N/A", "not determined", etc.
    "sd", "se", "ci",  # statistics: std dev, std error, confidence interval
    "lr", "ml", "dl", "nn", "rf", "svm",  # ML abbreviations
    # Chemical/physics
    "au", "ag", "cu", "fe", "zn",  # element symbols
    "ph", "uv", "dc", "ac", "rf",  # physics terms
})

# Specific pattern for -tion/-sion/-xion/-cion OCR breaks.
# "on" is blocked by _COMMON_SHORT_WORDS in the general regex, but in
# "-tion" context it's clearly a suffix fragment, not a separate word.
# E.g., "Descripti on" → "Description", "dimensi on" → "dimension".
_ION_BREAK_RE = re.compile(r"([a-zA-Z]{3,}[tsxcTSXC][iI])\s([oO][nN])(?=\s|$)")

# Known OCR-break patterns discovered from real-world PDFs.
# Single-letter breaks ("Subsyste m") are too ambiguous for regex
# (they match math variables like "variable z"), so they go here.
# Longer breaks (3+ trailing chars) also go here.
# All-uppercase breaks also go here since regex blocks all uppercase pairs.
# The learning pipeline adds new patterns as it processes more PDFs.
_KNOWN_LONG_BREAKS: dict[str, str] = {
    # Single-letter OCR breaks (moved here because regex can't distinguish
    # from math variables, signal names, etc.)
    "Subsyste m": "Subsystem",
    "subsyste m": "subsystem",
    "SUBSYSTE M": "SUBSYSTEM",
    # Multi-char OCR breaks too risky for regex
    "Asynchro nous": "Asynchronous",
    "SUBSY STEM": "SUBSYSTEM",
    # All-uppercase OCR breaks (regex blocks all uppercase pairs to avoid
    # merging abbreviation pairs like "GOTO CC", "LLVM IR")
    "EXECU TE": "EXECUTE",
}

# Pattern: underscore-identifier split by space ("bht_updat e_i" → "bht_update_i")
_BROKEN_IDENT_RE = re.compile(r"(\w+_\w{2,})\s([a-zA-Z]{1,6})(_\w+)")


def normalize_cell(val: Any) -> str:
    """Normalize whitespace in cell text (benign transformation).

    Converts newlines and non-breaking spaces to regular spaces and
    collapses runs of whitespace. This is NOT counted as fragmentation
    because newlines within cells are normal PDF content.
    """
    if val is None:
        return ""
    text = str(val).replace("\u00a0", " ").replace("\n", " ")
    return " ".join(text.split()).strip()


def _fix_broken_words(text: str) -> str:
    """Fix OCR-broken words using generalizable patterns.

    Three-tier approach:
    1. Specific suffix patterns: -tion/-sion/-xion breaks (safe, high-confidence)
    2. General regex + stopword filter: merges non-word trailing fragments
    3. Lookup: handles known longer breaks discovered from real PDFs

    The stopword filter prevents merging common English short words
    ("vibration to" stays as-is, "EXECU TE" gets merged).
    """
    # Fix underscore-identifier splits first ("bht_updat e_i" → "bht_update_i")
    text = _BROKEN_IDENT_RE.sub(r"\1\2\3", text)

    # Apply known longer breaks from lookup table
    for old, new in _KNOWN_LONG_BREAKS.items():
        text = text.replace(old, new)

    # Fix -tion/-sion/-xion breaks before stopword filter blocks "on"
    text = _ION_BREAK_RE.sub(lambda m: m.group(1) + m.group(2), text)

    # Fix general broken words (2-char trailing only) with stopword filter
    def _merge_broken(m: re.Match) -> str:
        trailing = m.group(2)
        first = m.group(1)
        # Don't merge if trailing fragment is a common English word
        if trailing.lower() in _COMMON_SHORT_WORDS:
            return m.group(0)
        # Don't merge two all-uppercase words (likely separate abbreviations)
        # e.g., "GOTO CC", "LLVM IR", "HVN HU" — abbreviation pairs, not OCR
        if trailing.isupper() and first.isupper():
            return m.group(0)
        # Don't merge uppercase abbreviation after mixed-case word
        # (e.g., "Programming IO", "alias HW" — abbreviations, not OCR breaks)
        if trailing.isupper() and not first.isupper():
            return m.group(0)
        # Don't merge CamelCase trailing (e.g., "Ua", "Tr", "Rq") — these are
        # math variables, author names, or abbreviations, not OCR fragments.
        # Real OCR breaks have all-uppercase ("TE") or all-lowercase ("on") trailing.
        if trailing[0].isupper() and not trailing.isupper():
            return m.group(0)
        return m.group(1) + m.group(2)

    # Apply iteratively (a word may be broken in multiple places)
    prev = None
    while prev != text:
        prev = text
        text = _BROKEN_WORD_RE.sub(_merge_broken, text)

    return text


def _fix_direction_tokens(text: str) -> str:
    """Fix direction token cells like 'ou t' → 'out', 'in/out'."""
    tokens = text.split()
    if not tokens or not all(tok.lower() in {"in", "out", "ou", "t"} for tok in tokens):
        return text
    merged: List[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i].lower()
        if tok == "in":
            merged.append("in")
        elif tok == "out":
            merged.append("out")
        elif tok == "ou" and i + 1 < len(tokens) and tokens[i + 1].lower() == "t":
            merged.append("out")
            i += 1
        else:
            merged.append(tok)
        i += 1
    return "/".join(merged)


def sanitize_cell(val: Any) -> str:
    """Full sanitization: normalize whitespace + fix OCR errors.

    This is the public API used by downstream code that needs clean text.
    For fragmentation scoring, use fragmentation_score() which only counts
    OCR-level changes (not whitespace normalization).
    """
    text = normalize_cell(val)
    text = _fix_broken_words(text)
    text = _fix_direction_tokens(text)
    return text


def fragmentation_score(df: pd.DataFrame) -> int:
    """Count cells with actual OCR errors (broken words, split identifiers).

    Only counts cells where OCR error fixing changes the text AFTER whitespace
    normalization. Newline-to-space and NBSP-to-space conversions are NOT counted
    because they are normal PDF content, not extraction errors.
    """
    count = 0
    for cell in df.astype(str).values.flatten():
        normalized = normalize_cell(cell)
        fixed = _fix_broken_words(normalized)
        fixed = _fix_direction_tokens(fixed)
        if fixed != normalized:
            count += 1
    return count


def should_retry_fragmentation(score: int) -> bool:
    """Check if fragmentation score exceeds retry threshold."""
    return score > max(0, int(os.getenv("TABLE_FRAGMENTATION_RETRY_THRESHOLD", "0")))


def has_fragmentation_improvement(existing: int, new: int) -> bool:
    """Check if new fragmentation score is significantly better than existing."""
    return (existing - new) >= max(1, int(os.getenv("TABLE_FRAGMENTATION_MIN_IMPROVEMENT", "1")))


def should_replace_table(
    existing_frag: int, new_frag: int, existing_score: float, new_score: float
) -> bool:
    """Decide if a new table extraction is better than an existing one."""
    if has_fragmentation_improvement(existing_frag, new_frag):
        return True
    if new_frag == existing_frag and new_score > existing_score:
        return True
    return False


# Extended stopwords for scientific domain papers (arXiv, etc.)
# Used when domain="scientific" in fragmentation_score_with_domain()
_SCIENTIFIC_STOPWORDS = frozenset({
    # All common short words
    *_COMMON_SHORT_WORDS,
    # Mathematical functions and operators
    "max", "min", "arg", "lim", "sup", "inf", "det", "dim", "ker", "dom",
    "sin", "cos", "tan", "log", "exp", "mod", "gcd", "lcm",
    # Statistical terms
    "avg", "std", "var", "cov", "cor", "iid", "iff", "wrt",
    # Common paper abbreviations
    "fig", "tab", "sec", "ref", "app", "def", "thm", "lem", "cor", "prop",
    # ML/AI terms
    "mlp", "rnn", "cnn", "gan", "vae", "llm", "nlp", "ocr", "gpu", "cpu", "tpu",
    # LaTeX commands that sometimes appear in extracted text
    "frac", "sqrt", "sum", "prod", "int", "lim", "vec", "hat", "bar",
})


def fragmentation_score_with_domain(df: pd.DataFrame, domain: str = "general") -> int:
    """Count cells with OCR errors, with domain-specific filtering.

    For scientific papers (domain="scientific"), uses an extended stopword list
    that includes math functions, statistical terms, and common abbreviations
    to reduce false positives from single-letter variables and abbreviated terms.

    Args:
        df: DataFrame to analyze
        domain: Document domain ("scientific", "engineering", "general")

    Returns:
        Count of cells with detected OCR fragmentation
    """
    # Select stopword set based on domain
    if domain == "scientific":
        stopwords = _SCIENTIFIC_STOPWORDS
    else:
        stopwords = _COMMON_SHORT_WORDS

    count = 0
    for cell in df.astype(str).values.flatten():
        normalized = normalize_cell(cell)
        fixed = _fix_broken_words_with_stopwords(normalized, stopwords)
        fixed = _fix_direction_tokens(fixed)
        if fixed != normalized:
            count += 1
    return count


def _fix_broken_words_with_stopwords(text: str, stopwords: frozenset) -> str:
    """Fix OCR-broken words using a custom stopword set.

    Identical to _fix_broken_words() but accepts a custom stopword set
    for domain-specific filtering.
    """
    # Fix underscore-identifier splits first
    text = _BROKEN_IDENT_RE.sub(r"\1\2\3", text)

    # Apply known longer breaks from lookup table
    for old, new in _KNOWN_LONG_BREAKS.items():
        text = text.replace(old, new)

    # Fix -tion/-sion/-xion breaks before stopword filter blocks "on"
    text = _ION_BREAK_RE.sub(lambda m: m.group(1) + m.group(2), text)

    # Fix general broken words with provided stopword filter
    def _merge_broken(m: re.Match) -> str:
        trailing = m.group(2)
        first = m.group(1)
        # Don't merge if trailing fragment is in stopwords
        if trailing.lower() in stopwords:
            return m.group(0)
        # Don't merge two all-uppercase words
        if trailing.isupper() and first.isupper():
            return m.group(0)
        # Don't merge uppercase abbreviation after mixed-case word
        if trailing.isupper() and not first.isupper():
            return m.group(0)
        # Don't merge CamelCase trailing
        if trailing[0].isupper() and not trailing.isupper():
            return m.group(0)
        return m.group(1) + m.group(2)

    # Apply iteratively
    prev = None
    while prev != text:
        prev = text
        text = _BROKEN_WORD_RE.sub(_merge_broken, text)

    return text
