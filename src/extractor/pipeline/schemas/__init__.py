"""
Pydantic schemas for validating LLM outputs in the extractor pipeline.

These schemas formalize the implicit JSON contracts in prompt files,
enabling fail-fast validation and better error diagnostics.
"""

from extractor.pipeline.schemas.reflow import (
    ReflowOutput,
    ReflowedJson,
    ParagraphBlock,
    ListBlock,
    TableBlock,
    FigureBlock,
)
from extractor.pipeline.schemas.summarizer import SummaryOutput
from extractor.pipeline.schemas.llm_call import LLMCallRecord

__all__ = [
    "ReflowOutput",
    "ReflowedJson",
    "ParagraphBlock",
    "ListBlock",
    "TableBlock",
    "FigureBlock",
    "SummaryOutput",
    "LLMCallRecord",
]

