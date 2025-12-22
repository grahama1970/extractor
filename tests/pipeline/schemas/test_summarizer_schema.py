"""
Unit tests for summarizer schema validation.
"""

import pytest
from pydantic import ValidationError

from extractor.pipeline.schemas.summarizer import (
    SummaryOutput,
    CheckpointSummary,
    validate_summary_output,
)


class TestSummaryOutput:
    def test_valid_summary(self):
        data = {
            "summary": "This section describes the authentication flow.",
            "key_concepts": ["auth", "token", "session"],
        }
        output = SummaryOutput.model_validate(data)
        assert len(output.key_concepts) == 3

    def test_minimal_summary(self):
        data = {"summary": "Brief summary."}
        output = SummaryOutput.model_validate(data)
        assert output.key_concepts == []
        assert output.confidence == 1.0

    def test_with_optional_fields(self):
        data = {
            "summary": "Test",
            "key_concepts": ["a"],
            "section_id": "sec_001",
            "confidence": 0.8,
        }
        output = SummaryOutput.model_validate(data)
        assert output.section_id == "sec_001"
        assert output.confidence == 0.8

    def test_confidence_bounds(self):
        # Valid bounds
        SummaryOutput.model_validate({"summary": "x", "confidence": 0.0})
        SummaryOutput.model_validate({"summary": "x", "confidence": 1.0})

        # Out of bounds
        with pytest.raises(ValidationError):
            SummaryOutput.model_validate({"summary": "x", "confidence": 1.1})

        with pytest.raises(ValidationError):
            SummaryOutput.model_validate({"summary": "x", "confidence": -0.1})


class TestCheckpointSummary:
    def test_valid_checkpoint(self):
        cp = CheckpointSummary(
            checkpoint_name="Chapter 1",
            summary="Covers introduction",
            covered_sections=["sec_001", "sec_002"],
        )
        assert len(cp.covered_sections) == 2

    def test_minimal_checkpoint(self):
        cp = CheckpointSummary(checkpoint_name="Ch1", summary="Test")
        assert cp.covered_sections == []


class TestValidateSummaryOutput:
    def test_valid_returns_output(self):
        data = {"summary": "Test summary", "key_concepts": ["a", "b"]}
        output, error = validate_summary_output(data)
        assert output is not None
        assert error is None

    def test_missing_required_field(self):
        data = {"key_concepts": ["a"]}  # Missing summary
        output, error = validate_summary_output(data)
        assert output is None
        assert error is not None
