"""
Actual schema for Stage 07 (Reflow) real outputs.

This schema matches the actual JSON structure produced by the pipeline,
as opposed to the idealized LLM schema in reflow.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, field_validator


class BlockMetadata(BaseModel):
    """Metadata for a block in reflowed output."""

    font_info: Optional[Dict[str, Any]] = None
    color: Optional[str] = None
    bbox: Optional[List[float]] = None


class BlockType(BaseModel):
    """Base block type with common fields."""

    block_type: str
    page_idx: int
    page: int
    text: str
    bbox: Optional[List[float]] = None
    id: Optional[str] = None


class SectionHeaderBlock(BlockType):
    """Section header block."""

    block_type: Literal["SectionHeader"]
    first_span_font: Dict[str, Any]
    surya_confidence: float
    quality_score: float
    is_suspicious: bool
    block_id: int
    section_titles: List[str]
    section_hashes: List[str]
    section_number: str
    section_level: int
    section_depth: List[int]


class TextBlock(BlockType):
    """Regular text block."""

    block_type: Literal["Text"]
    spans: Optional[List[Dict[str, Any]]] = None


# Union type for all block types
ReflowBlock = SectionHeaderBlock | TextBlock | Dict[str, Any]  # Fallback for unknown types


class Metadata(BaseModel):
    """Section metadata."""

    section_id: str
    hash: str
    section_titles: List[str]
    section_numbers: List[str]
    section_level: int
    section_depth: List[int]
    section_breadcrumbs: List[str]


class ReflowedSection(BaseModel):
    """A reflowed section with title, blocks, and metadata."""

    title: str
    level: int
    blocks: List[ReflowBlock]
    metadata: Metadata


class SourceFiles(BaseModel):
    """Paths to source files used in reflow."""

    sections: str
    tables: Optional[str] = None
    figures: Optional[str] = None
    annotations: Optional[str] = None


class Reflow07Output(BaseModel):
    """
    Complete Stage 07 actual output schema.

    This matches the real structure produced by 07_reflow_section.py
    """

    timestamp: datetime
    source_files: SourceFiles
    status: Literal["Completed", "Failed"]
    section_count: int
    reflowed_sections: List[ReflowedSection]


def validate_reflow07_output(data: dict) -> tuple[Reflow07Output | None, str | None]:
    """
    Validate Stage 07 reflow output against actual schema.

    Returns (Reflow07Output, None) on success, (None, error_str) on failure.
    """
    try:
        output = Reflow07Output.model_validate(data)
        return output, None
    except Exception as e:
        return None, f"Reflow07Output validation failed: {str(e)}"


# Add validation helper that handles depth coercion
@field_validator("section_depth", mode="before")
def coerce_section_depth(cls, v):
    """Handle the common issue where section_depth might be int instead of list."""
    if isinstance(v, int):
        return [v]
    return v


# Apply the validator to the section depth fields
SectionHeaderBlock.model_rebuild()
Metadata.model_rebuild()
