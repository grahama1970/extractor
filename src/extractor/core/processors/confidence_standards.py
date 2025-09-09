"""
MARKER FORK ADDITION - Surya Confidence Enhancement

Confidence scoring standards for PDF extraction validation.

This module defines standardized confidence scores and quality metrics
used across all processors to ensure consistent validation.
"""

from typing import Dict, Tuple, Optional
from enum import Enum


class ConfidenceLevel(Enum):
    """Standardized confidence levels for validation."""
    
    # Very high confidence (0.8-1.0)
    VERY_HIGH = "very_high"  # 0.8-1.0: Almost certain
    
    # High confidence (0.6-0.8)
    HIGH = "high"  # 0.6-0.8: Likely correct
    
    # Medium confidence (0.4-0.6)
    MEDIUM = "medium"  # 0.4-0.6: Uncertain, needs review
    
    # Low confidence (0.2-0.4)
    LOW = "low"  # 0.2-0.4: Probably wrong
    
    # Very low confidence (0.0-0.2)
    VERY_LOW = "very_low"  # 0.0-0.2: Almost certainly wrong


class ValidationCategory(Enum):
    """Categories of validation issues."""
    
    # Content validation
    EMPTY_CONTENT = "empty_content"
    MINIMAL_CONTENT = "minimal_content"
    TRUNCATED_CONTENT = "truncated_content"
    
    # Type confusion
    TYPE_MISCLASSIFICATION = "type_misclassification"
    AMBIGUOUS_TYPE = "ambiguous_type"
    
    # Boundary issues
    PAGE_SPLIT = "page_split"
    COLUMN_SPLIT = "column_split"
    BLOCK_TRUNCATION = "block_truncation"
    ORPHANED_ELEMENT = "orphaned_element"
    
    # Structural issues
    MISSING_CONTINUATION = "missing_continuation"
    INCORRECT_MERGE = "incorrect_merge"
    BROKEN_SEQUENCE = "broken_sequence"
    
    # Quality issues
    OCR_ARTIFACT = "ocr_artifact"
    FORMATTING_ERROR = "formatting_error"
    LAYOUT_CONFUSION = "layout_confusion"


class ConfidenceScorer:
    """Standardized confidence scoring utilities."""
    
    # Score ranges for each confidence level
    SCORE_RANGES: Dict[ConfidenceLevel, Tuple[float, float]] = {
        ConfidenceLevel.VERY_HIGH: (0.8, 1.0),
        ConfidenceLevel.HIGH: (0.6, 0.8),
        ConfidenceLevel.MEDIUM: (0.4, 0.6),
        ConfidenceLevel.LOW: (0.2, 0.4),
        ConfidenceLevel.VERY_LOW: (0.0, 0.2),
    }
    
    # Default scores for common patterns
    DEFAULT_SCORES: Dict[ValidationCategory, float] = {
        # Content issues
        ValidationCategory.EMPTY_CONTENT: 0.9,  # Very high confidence it's empty
        ValidationCategory.MINIMAL_CONTENT: 0.7,  # High confidence it's minimal
        ValidationCategory.TRUNCATED_CONTENT: 0.5,  # Medium confidence
        
        # Type confusion
        ValidationCategory.TYPE_MISCLASSIFICATION: 0.4,  # Medium confidence
        ValidationCategory.AMBIGUOUS_TYPE: 0.3,  # Low confidence
        
        # Boundary issues
        ValidationCategory.PAGE_SPLIT: 0.7,  # High confidence
        ValidationCategory.COLUMN_SPLIT: 0.6,  # High confidence
        ValidationCategory.BLOCK_TRUNCATION: 0.4,  # Medium confidence
        ValidationCategory.ORPHANED_ELEMENT: 0.5,  # Medium confidence
        
        # Structural issues
        ValidationCategory.MISSING_CONTINUATION: 0.6,  # High confidence
        ValidationCategory.INCORRECT_MERGE: 0.4,  # Medium confidence
        ValidationCategory.BROKEN_SEQUENCE: 0.7,  # High confidence
        
        # Quality issues
        ValidationCategory.OCR_ARTIFACT: 0.8,  # Very high confidence
        ValidationCategory.FORMATTING_ERROR: 0.5,  # Medium confidence
        ValidationCategory.LAYOUT_CONFUSION: 0.4,  # Medium confidence
    }
    
    @classmethod
    def get_confidence_level(cls, score: float) -> ConfidenceLevel:
        """Get confidence level from numeric score."""
        for level, (min_score, max_score) in cls.SCORE_RANGES.items():
            if min_score <= score <= max_score:
                return level
        return ConfidenceLevel.VERY_LOW
    
    @classmethod
    def get_default_score(cls, category: ValidationCategory) -> float:
        """Get default confidence score for a validation category."""
        return cls.DEFAULT_SCORES.get(category, 0.5)
    
    @classmethod
    def adjust_score_for_context(cls, base_score: float, 
                                positive_indicators: int = 0,
                                negative_indicators: int = 0) -> float:
        """
        Adjust confidence score based on additional context.
        
        Args:
            base_score: Initial confidence score
            positive_indicators: Number of factors supporting the validation
            negative_indicators: Number of factors against the validation
            
        Returns:
            Adjusted confidence score (0.0-1.0)
        """
        # Each positive indicator increases confidence by 0.1
        # Each negative indicator decreases confidence by 0.1
        adjustment = (positive_indicators - negative_indicators) * 0.1
        
        # Apply adjustment and clamp to valid range
        adjusted_score = base_score + adjustment
        return max(0.0, min(1.0, adjusted_score))
    
    @classmethod
    def combine_scores(cls, scores: list[float], weights: Optional[list[float]] = None) -> float:
        """
        Combine multiple confidence scores.
        
        Args:
            scores: List of confidence scores
            weights: Optional weights for each score (must sum to 1.0)
            
        Returns:
            Combined confidence score
        """
        if not scores:
            return 0.5  # Default neutral confidence
        
        if weights:
            if len(weights) != len(scores):
                raise ValueError("Weights must match number of scores")
            if abs(sum(weights) - 1.0) > 0.01:
                raise ValueError("Weights must sum to 1.0")
            return sum(s * w for s, w in zip(scores, weights))
        else:
            # Simple average if no weights provided
            return sum(scores) / len(scores)


class MetadataStandards:
    """Standardized metadata field usage."""
    
    # Metadata field mappings for validation data
    VALIDATION_FIELDS = {
        # Use llm_error_count for boolean suspicious flag
        "is_suspicious": "llm_error_count",  # 0 = not suspicious, >0 = suspicious
        
        # Use previous_text for validation messages
        "validation_message": "previous_text",  # Prefixed with VALIDATION:
        
        # Use llm_tokens_used for confidence score
        "confidence_score": "llm_tokens_used",  # Score * 100 as integer
        
        # Additional structured data encoded in previous_text
        "boundary_info": "previous_text",  # Prefixed with BOUNDARY[type]:
        "type_confusion": "previous_text",  # Prefixed with TYPE_CONFUSION:
        "quality_issue": "previous_text",  # Prefixed with QUALITY:
    }
    
    # Prefixes for structured data in previous_text
    PREFIXES = {
        "validation": "VALIDATION:",
        "boundary": "BOUNDARY[{}]:",  # {} = boundary type
        "type_confusion": "TYPE_CONFUSION:",
        "quality": "QUALITY:",
        "merge_hint": "MERGE:",
    }
    
    @classmethod
    def encode_validation_data(cls, 
                              is_suspicious: bool,
                              category: ValidationCategory,
                              message: str,
                              confidence: float,
                              merge_suggestion: Optional[str] = None) -> Dict[str, any]:
        """
        Encode validation data into metadata fields.
        
        Returns:
            Dict with metadata field assignments
        """
        metadata = {}
        
        # Set suspicious flag
        metadata['llm_error_count'] = 1 if is_suspicious else 0
        
        # Encode confidence as integer (0-100)
        metadata['llm_tokens_used'] = int(confidence * 100)
        
        # Build structured message
        parts = []
        
        # Primary validation message
        parts.append(f"{cls.PREFIXES['validation']}{message}")
        
        # Category information
        parts.append(f"CATEGORY:{category.value}")
        
        # Merge suggestion if provided
        if merge_suggestion:
            parts.append(f"{cls.PREFIXES['merge_hint']}{merge_suggestion}")
        
        # Combine all parts
        metadata['previous_text'] = " | ".join(parts)
        
        return metadata
    
    @classmethod
    def decode_validation_data(cls, metadata: Dict[str, any]) -> Dict[str, any]:
        """
        Decode validation data from metadata fields.
        
        Returns:
            Dict with decoded validation information
        """
        result = {
            'is_suspicious': False,
            'message': None,
            'category': None,
            'confidence': None,
            'merge_suggestion': None,
        }
        
        # Check suspicious flag
        if metadata.get('llm_error_count', 0) > 0:
            result['is_suspicious'] = True
        
        # Decode confidence
        if metadata.get('llm_tokens_used', 0) > 0:
            result['confidence'] = metadata['llm_tokens_used'] / 100.0
        
        # Parse structured message
        previous_text = metadata.get('previous_text', '')
        if previous_text:
            parts = previous_text.split(' | ')
            
            for part in parts:
                if part.startswith(cls.PREFIXES['validation']):
                    result['message'] = part[len(cls.PREFIXES['validation']):]
                elif part.startswith('CATEGORY:'):
                    category_value = part[9:]  # len('CATEGORY:')
                    try:
                        result['category'] = ValidationCategory(category_value)
                    except ValueError:
                        pass
                elif part.startswith(cls.PREFIXES['merge_hint']):
                    result['merge_suggestion'] = part[len(cls.PREFIXES['merge_hint']):]
        
        return result


# Quality scoring rubric
class QualityRubric:
    """
    Standardized quality scoring rubric for blocks.
    
    Quality scores represent overall extraction quality (0.0-1.0):
    - 1.0: Perfect extraction, no issues
    - 0.8: Minor issues that don't affect understanding
    - 0.6: Moderate issues that may affect understanding
    - 0.4: Major issues that significantly affect understanding
    - 0.2: Severe issues, block barely usable
    - 0.0: Completely unusable
    """
    
    @classmethod
    def calculate_quality_score(cls,
                               has_content: bool,
                               content_completeness: float,
                               type_confidence: float,
                               boundary_confidence: float,
                               ocr_quality: float = 1.0) -> float:
        """
        Calculate overall quality score for a block.
        
        Args:
            has_content: Whether block has any content
            content_completeness: How complete the content is (0.0-1.0)
            type_confidence: Confidence in block type (0.0-1.0)
            boundary_confidence: Confidence in boundaries (0.0-1.0)
            ocr_quality: OCR quality estimate (0.0-1.0)
            
        Returns:
            Overall quality score (0.0-1.0)
        """
        if not has_content:
            return 0.0
        
        # Weighted components
        weights = {
            'content': 0.4,
            'type': 0.2,
            'boundary': 0.2,
            'ocr': 0.2,
        }
        
        components = {
            'content': content_completeness,
            'type': type_confidence,
            'boundary': boundary_confidence,
            'ocr': ocr_quality,
        }
        
        # Calculate weighted score
        quality_score = sum(
            components[key] * weights[key] 
            for key in weights
        )
        
        return max(0.0, min(1.0, quality_score))