#!/usr/bin/env python3
"""
Core Schema - Single Source of Truth for Data Contracts

This module defines the enumerated types and constants used for data flowing
through the pipeline. Using these enums prevents typos and "magic strings",
ensuring that all processors adhere to the same data contract.
"""
from enum import Enum

class BlockType(Enum):
    """Defines the type of a content block."""
    TEXT = "Text"
    SECTION_HEADER = "Section-header"
    LIST_ITEM = "List-item"
    TABLE = "Table"
    IMAGE = "Image"
    CODE = "Code"
    UNKNOWN = "Unknown"

class MetadataKey(Enum):
    """Defines keys for the 'metadata' dictionary within a block."""
    IS_SUSPICIOUS = "is_suspicious"
    SUSPICIOUS_REASON = "suspicious_reason"
    OVERRIDE_REASON = "override_reason"
    CONFIDENCE = "confidence"
    SOURCE_PROCESSOR = "source_processor"

class ProcessorType(Enum):
    """Defines the types of processors available in the pipeline."""
    ANNOTATION_LEARNING = "annotation_learning"
    MARKER_EXTRACTION = "marker_extraction"
    TEXT_CLEANING = "text_cleaning"
    BLOCK_MERGING = "block_merging"
    SECTION_HEADER_DETECTION = "section_header_detection"
    BLOCK_VERIFICATION = "block_verification"
    HIERARCHY_BUILDER = "hierarchy_builder"
    OUTPUT_RENDERER = "output_renderer"
    FONT_STYLE = "font_style"

class OutputFormat(Enum):
    """Supported output formats."""
    JSON = "json"
    ARANGODB = "arangodb"