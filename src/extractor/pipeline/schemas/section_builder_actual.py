"""
Actual schema for Stage 04 (Section Builder) real outputs.

This schema matches the actual JSON structure produced by the pipeline.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field


class SectionHeaderBlock(BaseModel):
    """Section header block with metadata."""

    block_type: Literal["SectionHeader"]
    page_idx: int
    page: int
    text: str
    first_span_font: Dict[str, Any]
    bbox: List[float]
    surya_confidence: float
    quality_score: float
    is_suspicious: bool
    block_id: int
    id: str
    section_titles: List[str]
    section_hashes: List[str]
    section_number: str
    section_level: int
    section_depth: List[int]
    section_breadcrumbs: List[str]


class TextBlock(BaseModel):
    """Regular text block."""

    block_type: Literal["Text", "Formula", "Title"]
    page_idx: int
    page: int
    text: str
    id: Optional[str] = None
    spans: Optional[List[Dict[str, Any]]] = None
    bbox: Optional[List[float]] = None


# Union type for all block types
SectionBlock = SectionHeaderBlock | TextBlock | Dict[str, Any]


class Metadata(BaseModel):
    """Section metadata with hierarchy and visual information."""

    section_number: str
    section_depth: List[int]
    section_hash: str
    block_count: int
    validation_method: str
    diagnostics: List[Any] = Field(default_factory=list)
    title_display: Optional[str] = None
    pages: List[int]
    page_start: int
    page_end: int
    page_count: int
    header_color_hex: Optional[str] = None
    header_color_bucket: Optional[str] = None
    composite_size_bytes: Optional[int] = None
    composite_width: Optional[int] = None
    composite_height: Optional[int] = None
    visual_path: Optional[str] = None
    breadcrumbs: Optional[List[str]] = None
    breadcrumb_titles: Optional[List[str]] = None


class Section(BaseModel):
    """A document section with title, blocks, and metadata."""

    title: str
    level: int
    display_title: str
    id: str
    parent_id: Optional[str] = None
    pages: List[int]
    page_start: int
    page_end: int
    bbox: List[float]
    has_visual: bool
    visual_path: Optional[str] = None
    metadata: Metadata
    blocks: List[SectionBlock]


class SuspiciousHeaderAnalysis(BaseModel):
    """Analysis of suspicious headers validation."""

    validation_method: str
    total_sections: int
    validated_sections: int
    suspicious_sections: int
    categories: Dict[str, List[str]] = Field(default_factory=dict)
    statistics: Dict[str, Any] = Field(default_factory=dict)


class SectionBuilder04Output(BaseModel):
    """
    Complete Stage 04 actual output schema.
    """

    success: bool
    timestamp: datetime
    source_json: str
    source_pdf: str
    status: Literal["Completed", "Failed"]
    section_count: int
    hierarchy_depth: int
    visual_captures: int
    suspicious_header_analysis: SuspiciousHeaderAnalysis
    sections: List[Section]
    timings: Dict[str, Any] = Field(default_factory=dict)
    resources: Dict[str, Any] = Field(default_factory=dict)
    run_id: str
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


def validate_sectionbuilder04_output(
    data: dict,
) -> tuple[SectionBuilder04Output | None, str | None]:
    """
    Validate Stage 04 section builder output against actual schema.
    """
    try:
        output = SectionBuilder04Output.model_validate(data)
        return output, None
    except Exception as e:
        return None, f"SectionBuilder04Output validation failed: {str(e)}"


def validate_single_section(data: dict) -> tuple[Section | None, str | None]:
    """
    Validate a single section entry.
    """
    try:
        section = Section.model_validate(data)
        return section, None
    except Exception as e:
        return None, f"Section validation failed: {str(e)}"
