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
    """Validate summary data and ensure key concepts are present."""
    def test_valid_summary(self):
        """Validate SummaryOutput model correctly parses valid key concepts."""
        data = {
            "summary": "This section describes the authentication flow.",
            "key_concepts": ["auth", "token", "session"],
        }
        output = SummaryOutput.model_validate(data)
        assert len(output.key_concepts) == 3

    def test_minimal_summary(self):
        """Validate summary data and return key concepts and confidence."""
        data = {"summary": "Brief summary."}
        output = SummaryOutput.model_validate(data)
        assert output.key_concepts == []
        assert output.confidence == 1.0

    def test_with_optional_fields(self):
        """Validate a summary output model with optional fields."""
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
    """Validate checkpoint summaries and their covered sections."""
    def test_valid_checkpoint(self):
        """Validate the number of covered sections in a checkpoint summary."""
        cp = CheckpointSummary(
            checkpoint_name="Chapter 1",
            summary="Covers introduction",
            covered_sections=["sec_001", "sec_002"],
        )
        assert len(cp.covered_sections) == 2

    def test_minimal_checkpoint(self):
        """Return covered sections from a checkpoint summary object."""
        cp = CheckpointSummary(checkpoint_name="Ch1", summary="Test")
        assert cp.covered_sections == []


class TestValidateSummaryOutput:
    """Validate summary output and check for required fields."""
    def test_valid_returns_output(self):
        """Validate summary output and return result with potential error."""
        data = {"summary": "Test summary", "key_concepts": ["a", "b"]}
        output, error = validate_summary_output(data)
        assert output is not None
        assert error is None

    def test_missing_required_field(self):
        """Validate output for missing required summary field in data."""
        data = {"key_concepts": ["a"]}  # Missing summary
        output, error = validate_summary_output(data)
        assert output is None
        assert error is not None
