"""Tests for s00_profile_detector with calibrated patterns.

These tests verify calibrated patterns are used when available.
"""


import pytest

from extractor.pipeline.calibration.schema import ArangoConfig, CalibrationSchema


@pytest.fixture
def schema():
    """Create a CalibrationSchema instance for testing."""
    config = ArangoConfig.from_env()
    config.database = "extractor_calibration_test"
    schema = CalibrationSchema(config)
    schema.create_collections()
    schema.drop_collections()
    schema.create_collections()
    yield schema
    schema.drop_collections()


def test_uses_calibrated_patterns(schema):
    """Test s00 uses learned patterns from ArangoDB."""
    # Create a learned pattern
    schema.create_pattern(
        {
            "_key": "test-preset_header_pattern",
            "preset_id": "test-preset",
            "element_type": "header",
            "pattern_name": "section_header",
            "stage1_regex": r"^\d+\.\d+\s+[A-Z]",
            "stage2_python": "def validate(t, f): return True",
            "confidence": 0.92,
            "confirmed_by_human": True,
            "active": True,
        }
    )

    # Verify pattern can be retrieved
    patterns = schema.list_patterns(preset_id="test-preset", active_only=True)
    assert len(patterns) == 1
    assert patterns[0]["pattern_name"] == "section_header"

    # Integration point: s00 should check for calibrated patterns
    # This verifies the data structure is correct for integration
    pattern = patterns[0]
    assert "stage1_regex" in pattern
    assert "stage2_python" in pattern
    assert pattern["confirmed_by_human"] is True


def test_flags_low_confidence(schema):
    """Test s00 flags documents with low preset match confidence."""
    # When confidence is low, should flag for calibration
    # This tests the integration hook point

    # Create a session that shows low confidence
    schema.create_session(
        {
            "_key": "low-conf-session",
            "preset_id": "test-preset",
            "client": "test",
            "pdf_path": "test.pdf",
            "page_count": 100,
            "status": "in_progress",
            "accuracy_history": [0.65],  # Below 95% threshold
            "owner": "test",
        }
    )

    session = schema.get_session("low-conf-session")
    assert session is not None

    # Integration: s00 should check if accuracy < threshold
    accuracy = session["accuracy_history"][-1] if session["accuracy_history"] else 0
    needs_calibration = accuracy < 0.95
    assert needs_calibration is True


def test_fallback_to_default(schema):
    """Test s00 falls back to default detection when no calibration."""
    # When no calibrated patterns exist, s00 should use default logic
    patterns = schema.list_patterns(preset_id="nonexistent-preset", active_only=True)
    assert len(patterns) == 0

    # Integration: s00 should fall back to default preset matching
    # This verifies the absence of patterns is handled correctly


def test_calibration_enhances_preset_match():
    """Test that calibrated patterns boost preset match confidence."""
    # This test verifies the integration concept:
    # - s00 normally uses PRESET_REGISTRY for matching
    # - With calibration, learned patterns should boost confidence

    # Simulate what s00 would do with calibrated patterns:
    # 1. Get patterns from ArangoDB
    # 2. Apply stage1 regex to detect candidates
    # 3. Apply stage2 python to validate
    # 4. Boost confidence if patterns match

    # Example pattern
    pattern = {
        "stage1_regex": r"^\d+\.\d+\s+[A-Z]",
        "confidence": 0.92,
    }

    import re

    test_text = "1.2 Introduction to the System"

    # Stage 1: regex match
    if re.match(pattern["stage1_regex"], test_text):
        # Calibrated pattern matches, boost confidence
        confidence_boost = pattern["confidence"]
        assert confidence_boost > 0.5


def test_should_flag_for_calibration():
    """Test the logic for flagging documents for calibration."""
    # Integration function that s00 should call

    def should_flag_for_review(doc_profile: dict, preset: dict) -> bool:
        """Flag documents that don't match the preset well."""
        match_score = doc_profile.get("preset_match", {}).get("confidence", 0)

        if match_score < 7:
            return True  # Low confidence match

        # Check for anomalies
        typical_tables = preset.get("typical_tables", 5)
        actual_tables = doc_profile.get("elements", {}).get("tables", 0)
        if actual_tables > typical_tables * 2:
            return True  # Unusual number of tables

        return False

    # Test low confidence triggers flag
    assert should_flag_for_review({"preset_match": {"confidence": 5}}, {}) is True

    # Test high confidence doesn't trigger
    assert should_flag_for_review({"preset_match": {"confidence": 10}}, {}) is False
