"""Calibration module for iterative preset calibration.

This module provides the library components for the doc-preset skill:
- ArangoDB schema and collections
- Data models for calibration sessions, examples, and patterns
- Page sampling for efficient human review
- Element detection with font/style metadata
- Pattern learning from human feedback
- Feedback handling and persistence
"""

from extractor.pipeline.calibration.schema import (
    CalibrationSchema,
    COLLECTION_SESSIONS,
    COLLECTION_EXAMPLES,
    COLLECTION_PATTERNS,
    EDGE_CONFIRMS,
)

from extractor.pipeline.calibration.models import (
    CalibrationSession,
    CalibrationExample,
    LearnedPattern,
    ConfirmEdge,
    SessionStatus,
    HumanVerdict,
    CreatedBy,
    Relationship,
    AgentDetection,
    Correction,
    ExpectedOutput,
    ExtractionHint,
)

from extractor.pipeline.calibration.sampler import (
    PageSampler,
    SamplerConfig,
    SampleResult,
    PageInfo,
    sample_pages,
)

from extractor.pipeline.calibration.detector import (
    ElementDetector,
    DetectorConfig,
    DetectedElement,
    FontInfo,
    detect_elements,
)

from extractor.pipeline.calibration.feedback_handler import FeedbackHandler

from extractor.pipeline.calibration.pattern_learner import (
    PatternLearner,
    PatternProposal,
    LearningResult,
    LLMJudgeResult,
)

from extractor.pipeline.calibration.verdict_parser import (
    parse_verdict,
    VerdictParseResult,
)

from extractor.pipeline.calibration.bbox_adjuster import (
    parse_bbox_adjustment,
    apply_adjustment,
    BboxAdjustment,
    AdjustmentType,
)

from extractor.pipeline.calibration.preset_generator import (
    generate_preset,
    write_preset_yaml,
    format_preset_summary,
    PresetConfig,
)

from extractor.pipeline.calibration.preview import (
    ExtractionPreview,
    PreviewResult,
    PagePreview,
    ElementSummary,
    format_preview_text,
    format_preview_json,
)

from extractor.pipeline.calibration.relations import (
    RelationType,
    RelationProposal,
    AnnotatedRelation,
    RelationDetector,
    RelationHandler,
    parse_relation_response,
    format_relation_summary,
)

from extractor.pipeline.calibration.timeout_learner import (
    TimeoutFeatures,
    TimeoutModel,
    collect_training_data,
    analyze_training_data,
    train_timeout_model,
    predict_timeout,
    save_timeout_model,
    load_timeout_model,
    validate_timeout_model,
    store_model_to_memory,
)

__all__ = [
    # Schema
    "CalibrationSchema",
    "COLLECTION_SESSIONS",
    "COLLECTION_EXAMPLES",
    "COLLECTION_PATTERNS",
    "EDGE_CONFIRMS",
    # Models
    "CalibrationSession",
    "CalibrationExample",
    "LearnedPattern",
    "ConfirmEdge",
    # Enums
    "SessionStatus",
    "HumanVerdict",
    "CreatedBy",
    "Relationship",
    # Nested models
    "AgentDetection",
    "Correction",
    "ExpectedOutput",
    "ExtractionHint",
    # Sampler
    "PageSampler",
    "SamplerConfig",
    "SampleResult",
    "PageInfo",
    "sample_pages",
    # Detector
    "ElementDetector",
    "DetectorConfig",
    "DetectedElement",
    "FontInfo",
    "detect_elements",
    # Feedback handler
    "FeedbackHandler",
    # Pattern learner
    "PatternLearner",
    "PatternProposal",
    "LearningResult",
    "LLMJudgeResult",
    # Verdict parser
    "parse_verdict",
    "VerdictParseResult",
    # Bbox adjuster
    "parse_bbox_adjustment",
    "apply_adjustment",
    "BboxAdjustment",
    "AdjustmentType",
    # Preset generator
    "generate_preset",
    "write_preset_yaml",
    "format_preset_summary",
    "PresetConfig",
    # Preview
    "ExtractionPreview",
    "PreviewResult",
    "PagePreview",
    "ElementSummary",
    "format_preview_text",
    "format_preview_json",
    # Relations
    "RelationType",
    "RelationProposal",
    "AnnotatedRelation",
    "RelationDetector",
    "RelationHandler",
    "parse_relation_response",
    "format_relation_summary",
    # Timeout learner
    "TimeoutFeatures",
    "TimeoutModel",
    "collect_training_data",
    "analyze_training_data",
    "train_timeout_model",
    "predict_timeout",
    "save_timeout_model",
    "load_timeout_model",
    "validate_timeout_model",
    "store_model_to_memory",
]
