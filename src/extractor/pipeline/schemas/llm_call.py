"""
Pydantic schema for LLM call telemetry records.

Used by log_llm_call() in debug_utils.py to stamp LLM calls
with standardized metadata for observability.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


TaskKind = Literal[
    "reflow",
    "summarize",
    "verify_header",
    "extract_requirements",
    "lean4_formalize",
    "figure_describe",
    "table_repair",
    "checkpoint_summary",
]


class LLMCallRecord(BaseModel):
    """
    Telemetry record for a single LLM call.

    Written to per-stage timings.jsonl for observability.
    """

    ts: str = Field(description="ISO timestamp")
    stage: str = Field(description="Stage name, e.g. '07_reflow_section'")
    task_kind: str = Field(description="Type of task: reflow, summarize, verify_header, etc.")
    route: Literal["chutes/text", "chutes/vlm"] = Field(
        description="Logical route: text or vision model"
    )
    model: str = Field(description="Underlying model ID from env")
    section_id: str | None = Field(default=None, description="Section or unit-of-work ID")
    success: bool = Field(description="Whether the call succeeded")
    error_class: str | None = Field(
        default=None,
        description="Error classification: timeout, parse_fail, validation_fail, api_error",
    )
    latency_ms: int | None = Field(default=None, description="Call latency in milliseconds")
    tokens_in: int | None = Field(default=None, description="Input token count if available")
    tokens_out: int | None = Field(default=None, description="Output token count if available")
    attempt_count: int | None = Field(
        default=None, description="Number of attempts (null if unknown)"
    )
    raw_preview: str | None = Field(
        default=None, description="First 400 chars of response on error paths only"
    )

    model_config = {"extra": "forbid"}  # Fail on unexpected fields


def validate_llm_call_record(data: dict) -> tuple[LLMCallRecord | None, str | None]:
    """
    Validate an LLM call record and return (record, error_message).

    Returns (LLMCallRecord, None) on success, (None, error_str) on failure.
    """
    try:
        return LLMCallRecord.model_validate(data), None
    except Exception as e:
        return None, str(e)
