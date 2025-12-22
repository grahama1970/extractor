"""
Pydantic schema for Stage 07 (reflow_section) LLM outputs.

Matches the JSON schema defined in prompts/07_reflow_section.json.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, field_validator


class ParagraphBlock(BaseModel):
    """A paragraph block in reflowed output."""

    type: Literal["paragraph"]
    text: str


class ListBlock(BaseModel):
    """A list block in reflowed output."""

    type: Literal["list"]
    items: list[str]


class TableBlock(BaseModel):
    """A table block in reflowed output."""

    type: Literal["table"]
    id: str
    title: str | None = None
    columns: list[str]
    rows: list[list[str]]

    @field_validator("rows")
    @classmethod
    def rows_match_columns(cls, v: list[list[str]], info) -> list[list[str]]:
        """Validate that each row has the same length as columns."""
        # info.data contains the already-validated fields
        columns = info.data.get("columns", [])
        if columns:
            for i, row in enumerate(v):
                if len(row) != len(columns):
                    raise ValueError(
                        f"Row {i} has {len(row)} cells but expected {len(columns)} (columns count)"
                    )
        return v


class FigureBlock(BaseModel):
    """A figure block in reflowed output."""

    type: Literal["figure"]
    id: str
    image_ref: str
    caption: str | None = None


# Discriminated union for block types
ReflowBlock = Annotated[
    Union[ParagraphBlock, ListBlock, TableBlock, FigureBlock],
    Field(discriminator="type"),
]


class ReflowedJson(BaseModel):
    """The reflowed_json structure containing title and blocks."""

    title: str | None = None
    blocks: list[ReflowBlock] = Field(default_factory=list)


class ReflowOutput(BaseModel):
    """
    Complete Stage 07 LLM output schema.

    Matches the JSON schema in prompts/07_reflow_section.json.
    """

    reflowed_json: ReflowedJson
    ocr_corrections: dict[str, str] = Field(default_factory=dict)
    improvements_made: str = ""
    summary: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)

    @classmethod
    def from_dict(cls, data: dict) -> "ReflowOutput":
        """Parse from a dict, handling nested reflowed_json."""
        # Handle case where reflowed_json might be a dict
        if isinstance(data.get("reflowed_json"), dict):
            data["reflowed_json"] = ReflowedJson.model_validate(data["reflowed_json"])
        return cls.model_validate(data)


# For backward compatibility with code expecting a plain dict check
def validate_reflow_output(data: dict) -> tuple[ReflowOutput | None, str | None]:
    """
    Validate reflow output and return (validated_output, error_message).

    Returns (ReflowOutput, None) on success, (None, error_str) on failure.
    """
    try:
        return ReflowOutput.model_validate(data), None
    except Exception as e:
        return None, str(e)
