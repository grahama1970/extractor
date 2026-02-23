"""
Actual schema for Stage 09 (Section Summarizer) real outputs.

This schema matches the actual JSON structure produced by the pipeline,
as opposed to the idealized LLM schema in summarizer.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class SummaryData(BaseModel):
    """Summary data for a regular section."""

    summary: str
    key_concepts: List[str] = Field(default_factory=list)


class CheckpointSummaryData(BaseModel):
    """Checkpoint summary data with additional fields."""

    checkpoint_summary: str
    major_themes: List[str] = Field(default_factory=list)
    key_concepts: List[str] = Field(default_factory=list)
    chapter_purpose: str


class Summary(BaseModel):
    """A single summary entry with metadata."""

    section_id: str
    section_title: str
    section_level: int
    summary_data: SummaryData | CheckpointSummaryData
    success: bool
    is_checkpoint: Optional[bool] = False
    sections_covered: Optional[int] = None


class Summarizer09Output(BaseModel):
    """
    Complete Stage 09 actual output schema.

    This matches the real structure produced by 09_section_summarizer.py
    """

    timestamp: datetime
    source_json: str
    status: Literal["Completed", "Failed"]
    sections_processed: int
    summaries_generated: int
    summaries: List[Summary]


def validate_summarizer09_output(data: dict) -> tuple[Summarizer09Output | None, str | None]:
    """
    Validate Stage 09 summarizer output against actual schema.

    Returns (Summarizer09Output, None) on success, (None, error_str) on failure.
    """
    try:
        output = Summarizer09Output.model_validate(data)
        return output, None
    except Exception as e:
        return None, f"Summarizer09Output validation failed: {str(e)}"
