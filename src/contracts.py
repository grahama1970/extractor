from __future__ import annotations

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict


class HeaderVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    doc_id: str
    section_id: str
    verdict: Literal["accept", "reject"]
    reasons: List[str] = Field(default_factory=list)
    prompt_version: str
    model_id: str


class ReflowedSection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    doc_id: str
    section_id: str
    reflowed_json: Dict[str, Any]
    ocr_corrections: Optional[Dict[str, Any] | List[str]] = None
    improvements_made: Optional[List[str] | str] = None
    summary: Optional[str] = None
    images_used: Optional[List[str]] = None
    prompt_version: str
    model_id: str


class SectionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    doc_id: str
    section_id: str
    summary_json: Dict[str, Any]
    prompt_version: str
    model_id: str


__all__ = [
    "HeaderVerdict",
    "ReflowedSection",
    "SectionSummary",
]
