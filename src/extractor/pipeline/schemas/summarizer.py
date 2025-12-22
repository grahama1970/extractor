"""
Pydantic schema for Stage 09 (section_summarizer) LLM outputs.

Matches the expected JSON structure from the summarizer prompts.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SummaryOutput(BaseModel):
    """
    Stage 09 section summary output schema.

    Expected keys based on the prompt and existing code patterns.
    """

    summary: str = Field(description="2-4 sentence summary of the section")
    key_concepts: list[str] = Field(
        default_factory=list,
        description="3-7 key concepts or terms from the section",
    )
    # Optional fields that may appear in some responses
    section_id: str | None = Field(default=None, description="ID of the summarized section")
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class CheckpointSummary(BaseModel):
    """
    Higher-level summary combining multiple section summaries.
    """

    checkpoint_name: str
    summary: str
    covered_sections: list[str] = Field(default_factory=list)


def validate_summary_output(data: dict) -> tuple[SummaryOutput | None, str | None]:
    """
    Validate summary output and return (validated_output, error_message).

    Returns (SummaryOutput, None) on success, (None, error_str) on failure.
    """
    try:
        return SummaryOutput.model_validate(data), None
    except Exception as e:
        return None, str(e)
