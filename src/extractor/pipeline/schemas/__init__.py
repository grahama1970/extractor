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
    validate_reflow_output,
)
from extractor.pipeline.schemas.summarizer import (
    SummaryOutput,
    validate_summary_output,
)
from extractor.pipeline.schemas.llm_call import (
    LLMCallRecord,
    validate_llm_call_record,
)

# Actual schemas that match real pipeline output
from extractor.pipeline.schemas.reflow_actual import (
    Reflow07Output,
    validate_reflow07_output,
)
from extractor.pipeline.schemas.summarizer_actual import (
    Summarizer09Output,
    validate_summarizer09_output,
)
from extractor.pipeline.schemas.section_builder_actual import (
    SectionBuilder04Output,
    validate_sectionbuilder04_output,
)

__all__ = [
    # Original schemas (LLM output formats)
    "ReflowOutput",
    "ReflowedJson",
    "ParagraphBlock",
    "ListBlock",
    "TableBlock",
    "FigureBlock",
    "SummaryOutput",
    "LLMCallRecord",
    "validate_reflow_output",
    "validate_summary_output",
    "validate_llm_call_record",

    # Actual schemas (pipeline output formats)
    "Reflow07Output",
    "Summarizer09Output",
    "SectionBuilder04Output",
    "validate_reflow07_output",
    "validate_summarizer09_output",
    "validate_sectionbuilder04_output",
]

