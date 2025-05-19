"""
Q&A-optimized configuration for Marker.

This configuration prioritizes accuracy over speed, ensuring the most complete
and accurate corpus extraction for downstream Q&A generation.
"""

from typing import List, Dict, Any
from pydantic import BaseModel, Field


class QAOptimizedConfig(BaseModel):
    """
    Configuration optimized for Q&A generation accuracy.
    
    Key features:
    - Comprehensive table extraction with validation
    - Full corpus validation against raw PDF
    - Multiple extraction methods for completeness
    - Camelot fallback for all low-confidence tables
    """
    
    # Prioritize accuracy over speed
    processing_mode: str = "accuracy"
    
    # Enable comprehensive validation
    enable_corpus_validation: bool = True
    corpus_validation_threshold: float = 0.97
    include_raw_corpus: bool = True
    
    # Table extraction settings
    table_extraction_mode: str = "comprehensive"
    table_confidence_threshold: float = 0.8
    always_validate_tables: bool = True
    use_camelot_fallback: bool = True
    camelot_fallback_threshold: float = 0.9  # Use Camelot for anything below 90%
    
    # Processor pipeline
    processors: List[str] = Field(default_factory=lambda: [
        # Standard processors (use actual processor classes that exist)
        "marker.processors.document_toc",
        "marker.processors.sectionheader",
        "marker.processors.line_merge",
        "marker.processors.text",
        
        # Enhanced table extraction
        "marker.processors.table",
        "marker.processors.enhanced_table_validator",  # New processor
        
        # Standard processing continues...
        "marker.processors.equation",
        "marker.processors.code",
        
        # Corpus validation before output
        "marker.processors.corpus_validator",  # New processor
        
        # Output processors
        "marker.processors.list",
        "marker.processors.reference"
    ])
    
    # Output settings to include validation data
    output_format_options: Dict[str, bool] = Field(default_factory=lambda: {
        "include_metadata": True,
        "include_validation_results": True,
        "include_raw_corpus": True,
        "include_table_confidence": True
    })
    
    # PyMuPDF settings for validation
    pymupdf_validation: Dict[str, Any] = Field(default_factory=lambda: {
        "extract_mode": "text",
        "preserve_whitespace": True,
        "dehyphenate": True
    })
    
    # Camelot settings for table extraction
    camelot_settings: Dict[str, Any] = Field(default_factory=lambda: {
        "flavor": "lattice",  # Better for bordered tables
        "accuracy": 0.9,
        "process_background": True,
        "line_scale": 40,
        "copy_text": ["v", "h"]  # Detect vertical and horizontal text
    })
    
    class Config:
        extra = 'allow'  # Allow additional fields for flexibility


def get_qa_optimized_config():
    """Get configuration optimized for Q&A generation."""
    return QAOptimizedConfig()