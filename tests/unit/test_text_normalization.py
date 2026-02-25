"""Tests for text normalization in extractors (PUA, ligatures, symbols)."""
import pytest


def test_pymupdf_normalize_pua_symbols():
    """PUA characters from Symbol/Wingdings fonts should be mapped to ASCII."""
    from extractor.pipeline.steps.s02_pymupdf_extractor import _normalize_text

    # Symbol font bullets
    assert "-" in _normalize_text("\uf0b7 Bullet item")
    assert "-" in _normalize_text("\uf0d8 Another bullet")

    # Checkboxes
    assert "[x]" in _normalize_text("\uf0fc Checked item")

    # Arrows
    assert "->" in _normalize_text("\uf0e0 Arrow")

    # Remaining PUA chars should be stripped
    assert "\uf0aa" not in _normalize_text("Text with \uf0aa unknown PUA")
    assert "\ue000" not in _normalize_text("Text with \ue000 private use")


def test_pymupdf_normalize_ligatures():
    """Ligature characters should be expanded to ASCII."""
    from extractor.pipeline.steps.s02_pymupdf_extractor import _normalize_text

    assert "file" in _normalize_text("a \ufb01le")
    assert "flow" in _normalize_text("a \ufb02ow")
    assert "efficient" in _normalize_text("e\ufb03cient")


def test_marker_normalize_pua_symbols():
    """PUA characters should be handled by marker extractor too."""
    from extractor.pipeline.steps.s02_marker_extractor import _normalize_text

    # Symbol font bullets
    assert "-" in _normalize_text("\uf0b7 Bullet item")
    assert "-" in _normalize_text("\uf0d8 Another bullet")

    # Remaining PUA chars should be stripped
    assert "\uf0aa" not in _normalize_text("Text with \uf0aa unknown PUA")


def test_marker_normalize_ligatures():
    """Ligature characters should be expanded by marker extractor."""
    from extractor.pipeline.steps.s02_marker_extractor import _normalize_text

    assert "file" in _normalize_text("a \ufb01le")
    assert "flow" in _normalize_text("a \ufb02ow")
    assert "efficient" in _normalize_text("e\ufb03cient")


def test_normalize_preserves_normal_text():
    """Normal ASCII text should pass through unchanged."""
    from extractor.pipeline.steps.s02_pymupdf_extractor import _normalize_text

    assert _normalize_text("Hello World") == "Hello World"
    assert _normalize_text("Section 1.2.3") == "Section 1.2.3"
    assert _normalize_text("The system shall comply.") == "The system shall comply."
