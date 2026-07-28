#!/usr/bin/env python3
"""Harvest OCR fragmentation training data from the 12TB corpus (v2).

Improved labeling: uses curated heuristics to distinguish true OCR breaks
from math-variable false positives. Generates a cleaner labeled dataset.

Label semantics:
  label=1  ->  likely OCR break (word was split by PDF extraction)
  label=0  ->  no OCR break (cell is fine as-is)

The key insight: true OCR breaks produce fragments that are NOT real words
or known math variables. E.g., "EXECU TE" is a break, but "lepton pT" is
a physics variable following a real word.
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from extractor.pipeline.utils.tables.metrics import (
    normalize_cell,
    sanitize_cell,
    _fix_broken_words,
    _fix_direction_tokens,
    _COMMON_SHORT_WORDS,
    _KNOWN_LONG_BREAKS,
)

# ── Improved labeling logic ────────────────────────────────────────

# Common math/physics single-letter and short variables that appear after
# real words in scientific papers. NOT OCR breaks.
_MATH_VARS = frozenset({
    "x", "y", "z", "t", "n", "m", "k", "r", "s", "p", "q", "u", "v", "w",
    "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "l",
    # Greek-spelled
    "alpha", "beta", "gamma", "delta", "epsilon", "eta", "theta",
    "lambda", "mu", "nu", "xi", "pi", "rho", "sigma", "tau", "phi", "chi", "psi", "omega",
    # Common short physics/math tokens
    "pT", "dY", "dX", "cV", "xT", "vt", "xt", "pt", "qt", "ht", "mt", "st", "rt",
    "gi", "nb", "vn", "ul", "ur", "uk", "si", "dk", "dh", "rd", "rs1", "rs2",
    "wP", "nk", "gs", "zs", "yj",
})

# Patterns that indicate a genuine OCR break (high confidence)
_REAL_BREAK_INDICATORS = [
    # Known lookup table entries
    lambda before, after, full: any(old in full for old in _KNOWN_LONG_BREAKS),
    # -tion/-sion/-xion breaks: "Descripti on" -> clearly OCR
    lambda before, after, full: (
        len(before) >= 3 and before[-1].lower() == "i"
        and before[-2].lower() in "tsxc" and after.lower() == "on"
    ),
    # Direction tokens: "ou t" -> "out"
    lambda before, after, full: (
        before.lower() == "ou" and after.lower() == "t"
    ),
    # Underscore identifiers: "bht_updat e_i"
    lambda before, after, full: "_" in before and "_" in full[full.index(before):],
]


def is_likely_ocr_break(text: str) -> bool:
    """Conservative check: is this text likely to contain a genuine OCR break?

    Returns True only for high-confidence OCR break patterns, filtering out
    math variables and abbreviations that the regex-based heuristic
    incorrectly merges.
    """
    normalized = normalize_cell(text)
    fixed = _fix_broken_words(normalized)
    fixed = _fix_direction_tokens(fixed)

    if fixed == normalized:
        return False  # No change at all

    # Find what spaces were removed
    tokens = normalized.split()
    if len(tokens) < 2:
        return False

    # Check each adjacent token pair for break indicators
    for i in range(len(tokens) - 1):
        before = tokens[i]
        after = tokens[i + 1]

        # Check high-confidence indicators
        for indicator in _REAL_BREAK_INDICATORS:
            if indicator(before, after, normalized):
                return True

        # Check: trailing fragment is a known math variable -> NOT a break
        if after in _MATH_VARS or after.lower() in _MATH_VARS:
            continue

        # Check: trailing fragment is in common short words -> NOT a break
        if after.lower() in _COMMON_SHORT_WORDS:
            continue

        # Check: trailing 1-char after a real English word -> likely math var
        if len(after) == 1 and after.isalpha():
            continue

        # Check: trailing is 2 chars, all lowercase, after a capitalized word
        # This is often a math subscript: "polynomial pt", "sequence ht"
        if (len(after) == 2 and after.islower()
                and before[0].isupper() and len(before) >= 4):
            # Likely "Polynomial pt" pattern (math variable)
            continue

        # Check: trailing is 2 lowercase chars after a common English word
        # ending in a consonant cluster that doesn't suggest a break
        if len(after) == 2 and after.islower():
            # If the combined form is not a common English word, skip
            # (it's probably a math variable)
            combined = before + after
            # Simple heuristic: if the combined form has unusual letter patterns
            # at the join point, it might be a real break
            join_bigram = before[-1] + after[0]
            # Common English bigrams at join points in real OCR breaks
            common_break_bigrams = {
                "te", "ed", "er", "ly", "al", "le", "re", "ng", "ty",
                "ry", "ny", "dy", "fy", "gy", "ky", "my", "py", "wy",
            }
            if join_bigram.lower() not in common_break_bigrams:
                continue

        # If we get here, it might be a real break
        # But be conservative: require the trailing fragment to look like
        # a word suffix, not a standalone token
        if len(after) >= 2 and after.isalpha():
            return True

    return False


# ── Feature extraction ─────────────────────────────────────────────

def extract_features(raw_cell: str, use_conservative_label: bool = True) -> dict | None:
    """Extract features from a single raw cell string."""
    normalized = normalize_cell(raw_cell)
    if len(normalized) < 2:
        return None

    sanitized = sanitize_cell(raw_cell)
    heuristic_changed = sanitized != normalized

    if use_conservative_label:
        label = 1 if is_likely_ocr_break(normalized) else 0
    else:
        label = 1 if heuristic_changed else 0

    tokens = normalized.split()
    has_space = len(tokens) > 1

    first_space_idx = normalized.find(" ")
    char_before_space = normalized[first_space_idx - 1] if first_space_idx > 0 else ""
    char_after_space = normalized[first_space_idx + 1] if first_space_idx >= 0 and first_space_idx + 1 < len(normalized) else ""

    left_word = tokens[0] if tokens else ""
    right_word = tokens[1] if len(tokens) > 1 else ""

    is_uppercase = normalized.isupper()
    has_underscore = "_" in normalized
    has_digit = bool(re.search(r"\d", normalized))
    has_hyphen = "-" in normalized

    alpha_count = sum(1 for c in normalized if c.isalpha())
    alpha_ratio = alpha_count / len(normalized) if normalized else 0.0

    # Additional features for v2
    # Check if any 2-char token follows a 3+ char token (the broken-word pattern)
    has_short_after_long = 0
    for i in range(len(tokens) - 1):
        if len(tokens[i]) >= 3 and 1 <= len(tokens[i + 1]) <= 2 and tokens[i + 1].isalpha():
            has_short_after_long = 1
            break

    # Unicode/math content
    has_unicode_math = int(any(ord(c) > 127 for c in normalized))
    has_equals = int("=" in normalized)
    has_parens = int("(" in normalized or ")" in normalized)

    # Character class at join points
    # For each internal space, check if chars on both sides are alpha
    alpha_alpha_spaces = 0
    for i, ch in enumerate(normalized):
        if ch == " " and i > 0 and i < len(normalized) - 1:
            if normalized[i-1].isalpha() and normalized[i+1].isalpha():
                alpha_alpha_spaces += 1

    return {
        "text": normalized,
        "label": label,
        "heuristic_changed": int(heuristic_changed),
        # Numeric features
        "cell_len": len(normalized),
        "num_spaces": normalized.count(" "),
        "num_words": len(tokens),
        "left_word_len": len(left_word),
        "right_word_len": len(right_word),
        "alpha_ratio": round(alpha_ratio, 4),
        # Boolean features
        "has_space_in_middle": int(has_space),
        "is_uppercase": int(is_uppercase),
        "has_underscore": int(has_underscore),
        "has_digit": int(has_digit),
        "has_hyphen": int(has_hyphen),
        "has_short_after_long": has_short_after_long,
        "has_unicode_math": has_unicode_math,
        "has_equals": has_equals,
        "has_parens": has_parens,
        # Char-class features
        "char_before_space_is_alpha": int(char_before_space.isalpha()) if char_before_space else 0,
        "char_after_space_is_alpha": int(char_after_space.isalpha()) if char_after_space else 0,
        "char_before_space_is_upper": int(char_before_space.isupper()) if char_before_space else 0,
        "char_after_space_is_lower": int(char_after_space.islower()) if char_after_space else 0,
        "alpha_alpha_spaces": alpha_alpha_spaces,
    }


# ── Main harvester ─────────────────────────────────────────────────

def harvest(
    corpus_root: str = "/mnt/storage12tb/extractor_corpus/results",
    output_path: str = "/home/graham/workspace/experiments/pi-mono/.pi/skills/create-table-classifier/data/fragmentation_features.jsonl",
) -> None:
    """Harvest JSON table data from specified corpus directory."""
    pattern = os.path.join(corpus_root, "*", "05_table_extractor", "json_output", "05_tables.json")
    files = sorted(glob.glob(pattern))
    print(f"[harvest] Found {len(files)} S05 output files")

    total_cells = 0
    positive = 0
    negative = 0
    heuristic_changed_count = 0
    errors = 0

    with open(output_path, "w") as out:
        for idx, fpath in enumerate(files):
            try:
                with open(fpath) as f:
                    data = json.load(f)
            except Exception:
                errors += 1
                continue

            tables = data.get("tables", [])
            source = data.get("source_pdf", "")

            for t_idx, table in enumerate(tables):
                rows = table.get("pandas_df", [])
                for row in rows:
                    for col_key, cell_val in row.items():
                        total_cells += 1
                        feat = extract_features(cell_val)
                        if feat is None:
                            continue
                        feat["source_pdf"] = source
                        feat["table_index"] = t_idx
                        out.write(json.dumps(feat) + "\n")
                        if feat["label"] == 1:
                            positive += 1
                        else:
                            negative += 1
                        if feat["heuristic_changed"]:
                            heuristic_changed_count += 1

            if (idx + 1) % 100 == 0:
                print(f"  [{idx+1}/{len(files)}] cells={total_cells} pos={positive} neg={negative} heuristic_changed={heuristic_changed_count}")

    print(f"\n[harvest] Done.")
    print(f"  Total cells scanned:          {total_cells}")
    print(f"  Positive (true OCR break):    {positive}")
    print(f"  Negative (no break):          {negative}")
    print(f"  Heuristic changed (for ref):  {heuristic_changed_count}")
    print(f"  Skipped (empty/short):        {total_cells - positive - negative}")
    print(f"  File errors:                  {errors}")
    print(f"  Output: {output_path}")


if __name__ == "__main__":
    harvest()
