#!/usr/bin/env python3
"""Tests for HARDENS-pattern fixture extraction and fragmentation scoring.

Verifies that the fragmentation_score correctly distinguishes between:
- Benign whitespace normalization (newlines, NBSP) — NOT counted
- Actual OCR errors (broken words, split identifiers) — COUNTED

Also verifies that lattice strategies are not penalized for preserving
newlines within cells (the bug that caused stream_default to win 242/252
tables in HARDENS).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from extractor.pipeline.utils.tables.extraction import (
    CAMELOT_STRATEGIES,
    try_camelot_strategy,
)
from extractor.pipeline.utils.tables.metrics import (
    _fix_broken_words,
    _fix_direction_tokens,
    fragmentation_score,
    normalize_cell,
    sanitize_cell,
    score_table,
    should_replace_table,
)

FIXTURES_DIR = Path(__file__).parent


# ── normalize_cell: benign whitespace normalization ──────────────────────


class TestNormalizeCell:
    def test_newline_to_space(self):
        assert normalize_cell("hello\nworld") == "hello world"

    def test_nbsp_to_space(self):
        assert normalize_cell("hello\u00a0world") == "hello world"

    def test_whitespace_collapse(self):
        assert normalize_cell("  hello   world  ") == "hello world"

    def test_none(self):
        assert normalize_cell(None) == ""

    def test_multiline(self):
        assert normalize_cell("line1\nline2\nline3") == "line1 line2 line3"


# ── _fix_broken_words: OCR error detection ───────────────────────────────


class TestFixBrokenWords:
    """Generalizable broken-word detection using regex patterns."""

    def test_single_trailing_char_via_lookup(self):
        """Single-letter OCR breaks handled by _KNOWN_LONG_BREAKS lookup."""
        assert _fix_broken_words("Subsyste m") == "Subsystem"
        assert _fix_broken_words("subsyste m") == "subsystem"
        assert _fix_broken_words("SUBSYSTE M") == "SUBSYSTEM"

    def test_single_letter_math_variables_not_merged(self):
        """Single lowercase letters after words are math variables, not OCR."""
        assert _fix_broken_words("variable z") == "variable z"
        assert _fix_broken_words("targets t") == "targets t"
        assert _fix_broken_words("multiply s") == "multiply s"
        assert _fix_broken_words("dimension n") == "dimension n"
        assert _fix_broken_words("rate f") == "rate f"

    def test_two_trailing_chars(self):
        assert _fix_broken_words("EXECU TE") == "EXECUTE"
        assert _fix_broken_words("Descripti on") == "Description"
        assert _fix_broken_words("connexi on") == "connexion"

    def test_four_trailing_chars(self):
        assert _fix_broken_words("Asynchro nous") == "Asynchronous"

    def test_uppercase(self):
        assert _fix_broken_words("SUBSY STEM") == "SUBSYSTEM"

    def test_identifier_split(self):
        assert _fix_broken_words("bht_updat e_i") == "bht_update_i"
        assert _fix_broken_words("bht_predi ction_o") == "bht_prediction_o"

    def test_no_false_positive_normal_text(self):
        assert _fix_broken_words("hello world") == "hello world"
        assert _fix_broken_words("The system shall") == "The system shall"

    def test_no_false_positive_section_numbers(self):
        assert _fix_broken_words("Section 4.2.1") == "Section 4.2.1"

    def test_no_false_positive_short_words(self):
        assert _fix_broken_words("in out") == "in out"
        assert _fix_broken_words("See section 4") == "See section 4"

    def test_no_false_positive_prepositions(self):
        """Common prepositions/conjunctions must NOT be merged."""
        assert _fix_broken_words("vibration to") == "vibration to"
        assert _fix_broken_words("Division of") == "Division of"
        assert _fix_broken_words("calculated in") == "calculated in"
        assert _fix_broken_words("PowerPoint or") == "PowerPoint or"
        assert _fix_broken_words("satisfied by") == "satisfied by"
        assert _fix_broken_words("response is") == "response is"
        assert _fix_broken_words("will be") == "will be"
        assert _fix_broken_words("and if") == "and if"
        assert _fix_broken_words("hold at") == "hold at"
        assert _fix_broken_words("generates an") == "generates an"

    def test_no_false_positive_single_uppercase_labels(self):
        """Single uppercase letters after words are labels, not OCR breaks."""
        assert _fix_broken_words("Revision E") == "Revision E"
        assert _fix_broken_words("Annex B") == "Annex B"
        assert _fix_broken_words("Class A") == "Class A"
        assert _fix_broken_words("Appendix F") == "Appendix F"

    def test_no_false_positive_uppercase_abbreviations(self):
        """Uppercase abbreviations after mixed-case words are NOT OCR breaks."""
        assert _fix_broken_words("Programming IO") == "Programming IO"
        assert _fix_broken_words("alias HW") == "alias HW"
        assert _fix_broken_words("component UI") == "component UI"
        assert _fix_broken_words("different PC") == "different PC"

    def test_no_false_positive_versus(self):
        """'vs' is a common abbreviation (versus), not an OCR fragment."""
        assert _fix_broken_words("Loss vs Model") == "Loss vs Model"
        assert _fix_broken_words("Performance vs Steps") == "Performance vs Steps"

    def test_no_false_positive_roman_numerals(self):
        """Roman numerals should NOT be merged with preceding words."""
        assert _fix_broken_words("PART II") == "PART II"
        assert _fix_broken_words("TABLE II") == "TABLE II"
        assert _fix_broken_words("Section IV") == "Section IV"
        assert _fix_broken_words("Chapter VI") == "Chapter VI"

    def test_no_false_positive_camelcase_variables(self):
        """CamelCase trailing like 'Ua', 'Tr', 'Rq' are variables, not OCR."""
        assert _fix_broken_words("Response Ua") == "Response Ua"
        assert _fix_broken_words("Response Ub") == "Response Ub"
        assert _fix_broken_words("feature Rq") == "feature Rq"
        assert _fix_broken_words("vertices Ni") == "vertices Ni"

    def test_no_false_positive_all_uppercase_abbreviations(self):
        """All-uppercase abbreviation pairs should NOT be merged."""
        assert _fix_broken_words("DECOLLE FF") == "DECOLLE FF"
        assert _fix_broken_words("NASA SW") == "NASA SW"
        assert _fix_broken_words("GOTO CC") == "GOTO CC"
        assert _fix_broken_words("LLVM IR") == "LLVM IR"
        assert _fix_broken_words("HVN HU") == "HVN HU"

    def test_all_uppercase_ocr_breaks_via_lookup(self):
        """All-uppercase OCR breaks handled by _KNOWN_LONG_BREAKS lookup."""
        assert _fix_broken_words("EXECU TE") == "EXECUTE"

    def test_no_false_positive_programming_keywords(self):
        """Programming language keywords should NOT be merged."""
        assert _fix_broken_words("pub fn") == "pub fn"
        assert _fix_broken_words("async fn") == "async fn"
        assert _fix_broken_words("for ks") == "for ks"
        assert _fix_broken_words("type ty") == "type ty"
        assert _fix_broken_words("for ai") == "for ai"

    def test_no_false_positive_id_keyword(self):
        """'id' is a common abbreviation/keyword, not an OCR fragment."""
        assert _fix_broken_words("package id") == "package id"
        assert _fix_broken_words("action id") == "action id"

    def test_ion_suffix_still_caught(self):
        """Words ending in -tion/-sion/-xion should still be fixed despite 'on' stopword."""
        assert _fix_broken_words("Descripti on") == "Description"
        assert _fix_broken_words("connexi on") == "connexion"
        assert _fix_broken_words("informati on") == "information"
        assert _fix_broken_words("dimensi on") == "dimension"
        assert _fix_broken_words("DESCRIPTI ON") == "DESCRIPTION"

    def test_stopword_in_sentence_context(self):
        """Stopwords in realistic sentence fragments should NOT be merged."""
        assert _fix_broken_words("The system shall limit vibration to the crew") == \
            "The system shall limit vibration to the crew"
        assert _fix_broken_words("provisions of this standard") == \
            "provisions of this standard"
        assert _fix_broken_words("feedback on the design") == \
            "feedback on the design"


# ── _fix_direction_tokens ────────────────────────────────────────────────


class TestFixDirectionTokens:
    def test_ou_t_merge(self):
        assert _fix_direction_tokens("ou t") == "out"

    def test_in_out(self):
        assert _fix_direction_tokens("in out") == "in/out"

    def test_normal_text_unchanged(self):
        assert _fix_direction_tokens("hello world") == "hello world"


# ── sanitize_cell: full pipeline ─────────────────────────────────────────


class TestSanitizeCell:
    def test_full_pipeline(self):
        assert sanitize_cell("Subsyste m\nsplit") == "Subsystem split"

    def test_none(self):
        assert sanitize_cell(None) == ""

    def test_nbsp_and_ocr(self):
        assert sanitize_cell("EXECU\u00a0TE enable") == "EXECUTE enable"


# ── fragmentation_score: only counts OCR errors ─────────────────────────


class TestFragmentationScore:
    def test_newline_not_counted(self):
        """Newlines within cells should NOT be counted as fragmentation."""
        import pandas as pd

        df = pd.DataFrame([["hello\nworld", "clean"]])
        assert fragmentation_score(df) == 0

    def test_nbsp_not_counted(self):
        """Non-breaking spaces should NOT be counted as fragmentation."""
        import pandas as pd

        df = pd.DataFrame([["hello\u00a0world", "clean"]])
        assert fragmentation_score(df) == 0

    def test_ocr_error_counted(self):
        """Broken words SHOULD be counted as fragmentation."""
        import pandas as pd

        df = pd.DataFrame([["Subsyste m", "clean"]])
        assert fragmentation_score(df) == 1

    def test_mixed(self):
        """Only OCR errors count, not whitespace normalization."""
        import pandas as pd

        df = pd.DataFrame([
            ["hello\nworld", "Subsyste m"],
            ["text\u00a0here", "EXECU TE"],
        ])
        # Only "Subsyste m" and "EXECU TE" are OCR errors
        assert fragmentation_score(df) == 2


# ── Fixture extraction tests ────────────────────────────────────────────


def _get_fixture(name: str) -> Path:
    path = FIXTURES_DIR / name
    if not path.exists():
        pytest.skip(f"Fixture {name} not generated. Run generate_fixtures.py first.")
    return path


class TestCodeListingFixture:
    """Pattern 1: Tall code listing table with borders.

    Both lattice and stream should have EQUAL fragmentation scores.
    The old bug: lattice had frag=25 (newlines counted), stream had frag=3.
    """

    def test_lattice_stream_equal_fragmentation(self):
        pdf = _get_fixture("fixture_code_listing.pdf")
        lattice = try_camelot_strategy(
            pdf, 0, {"name": "lattice_default", **CAMELOT_STRATEGIES["lattice_default"]}
        )
        stream = try_camelot_strategy(
            pdf, 0, {"name": "stream_default", **CAMELOT_STRATEGIES["stream_default"]}
        )
        assert lattice and stream, "Both strategies must find tables"

        lattice_frag = fragmentation_score(lattice[0].df)
        stream_frag = fragmentation_score(stream[0].df)

        # Fragmentation should be equal (both only count OCR errors)
        assert lattice_frag == stream_frag, (
            f"Lattice frag ({lattice_frag}) should equal stream frag ({stream_frag}). "
            f"Newlines should not be counted as fragmentation."
        )


class TestLargeSpecFixture:
    """Pattern 3: Large spec table with NBSP and newlines in cells."""

    def test_fragmentation_only_ocr(self):
        pdf = _get_fixture("fixture_large_spec.pdf")
        lattice = try_camelot_strategy(
            pdf, 0, {"name": "lattice_default", **CAMELOT_STRATEGIES["lattice_default"]}
        )
        assert lattice, "Lattice must find the spec table"

        frag = fragmentation_score(lattice[0].df)
        score = score_table(lattice[0].df)

        # Fragmentation should be low — only OCR errors, not newlines
        assert frag < 5, f"Expected low fragmentation (OCR only), got {frag}"
        assert score > 100, f"Expected high score for large table, got {score}"


class TestWideMulticolFixture:
    """Pattern 4: Wide 15-column table."""

    def test_lattice_wins_wide_table(self):
        pdf = _get_fixture("fixture_wide_multicol.pdf")
        lattice = try_camelot_strategy(
            pdf, 0, {"name": "lattice_default", **CAMELOT_STRATEGIES["lattice_default"]}
        )
        stream = try_camelot_strategy(
            pdf, 0, {"name": "stream_default", **CAMELOT_STRATEGIES["stream_default"]}
        )
        assert lattice and stream, "Both strategies must find tables"

        l_score = score_table(lattice[0].df)
        s_score = score_table(stream[0].df)
        l_frag = fragmentation_score(lattice[0].df)
        s_frag = fragmentation_score(stream[0].df)

        # Lattice should win: higher score for wide tables
        assert l_score > s_score, (
            f"Lattice ({l_score}) should outscore stream ({s_score}) on wide tables"
        )
        # Both should have 0 fragmentation (no OCR errors in clean fixtures)
        assert l_frag == 0, f"Expected 0 lattice frag, got {l_frag}"
        assert s_frag == 0, f"Expected 0 stream frag, got {s_frag}"
