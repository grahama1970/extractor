"""Image description validators for LLM validation."""

from typing import Any, Dict, List, Optional
import re

from marker.core.llm_call.core.base import ValidationResult
from marker.core.llm_call.validators.base import BaseValidator
from marker.core.llm_call.core.strategies import validator


@validator("image_description")
class ImageDescriptionValidator(BaseValidator):
    """Validates image descriptions for completeness and quality."""
    
    def __init__(self,
                 min_length: int = 20,
                 max_length: Optional[int] = None,
                 required_elements: Optional[List[str]] = None,
                 forbidden_phrases: Optional[List[str]] = None):
        """Initialize image description validator.
        
        Args:
            min_length: Minimum description length
            max_length: Maximum description length
            required_elements: Elements that must be mentioned (e.g., 'color', 'shape', 'text')
            forbidden_phrases: Phrases to avoid (e.g., 'I cannot see', 'unclear')
        """
        self.min_length = min_length
        self.max_length = max_length
        self.required_elements = required_elements or []
        self.forbidden_phrases = forbidden_phrases or [
            "I cannot see",
            "I cannot describe",
            "image not found",
            "unable to process"
        ]
    
    @property
    def name(self) -> str:
        params = [f"min_length={self.min_length}"]
        if self.max_length:
            params.append(f"max_length={self.max_length}")
        if self.required_elements:
            params.append(f"required_elements={self.required_elements}")
        return f"image_description({', '.join(params)})"
    
    @property
    def description(self) -> str:
        return "Validates image descriptions for quality and completeness"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate image description."""
        # Extract description from response
        if hasattr(response, 'description'):
            description = response.description
        elif isinstance(response, dict) and 'description' in response:
            description = response['description']
        elif isinstance(response, str):
            description = response
        else:
            return ValidationResult(
                valid=False,
                error=f"Could not extract description from response type: {type(response)}"
            )
        
        errors = []
        suggestions = []
        
        # Check length
        desc_length = len(description.strip())
        if desc_length < self.min_length:
            errors.append(f"Description too short: {desc_length} < {self.min_length} characters")
            suggestions.append("Provide more detailed description")
        
        if self.max_length and desc_length > self.max_length:
            errors.append(f"Description too long: {desc_length} > {self.max_length} characters")
            suggestions.append("Make description more concise")
        
        # Check for forbidden phrases
        description_lower = description.lower()
        found_forbidden = []
        for phrase in self.forbidden_phrases:
            if phrase.lower() in description_lower:
                found_forbidden.append(phrase)
        
        if found_forbidden:
            errors.append(f"Found forbidden phrases: {', '.join(found_forbidden)}")
            suggestions.append("Remove error messages and provide actual description")
        
        # Check for required elements
        missing_elements = []
        for element in self.required_elements:
            if element.lower() not in description_lower:
                missing_elements.append(element)
        
        if missing_elements:
            errors.append(f"Missing required elements: {', '.join(missing_elements)}")
            suggestions.append(f"Include description of: {', '.join(missing_elements)}")
        
        if errors:
            return ValidationResult(
                valid=False,
                error="; ".join(errors),
                suggestions=suggestions,
                debug_info={
                    "length": desc_length,
                    "forbidden_found": found_forbidden,
                    "missing_elements": missing_elements
                }
            )
        
        return ValidationResult(
            valid=True,
            debug_info={
                "length": desc_length,
                "elements_found": [e for e in self.required_elements if e.lower() in description_lower]
            }
        )


@validator("alt_text")
class AltTextValidator(BaseValidator):
    """Validates alt text for accessibility compliance."""
    
    def __init__(self,
                 min_length: int = 10,
                 max_length: int = 125,
                 require_punctuation: bool = False):
        """Initialize alt text validator.
        
        Args:
            min_length: Minimum alt text length
            max_length: Maximum alt text length (125 is recommended)
            require_punctuation: Whether to require ending punctuation
        """
        self.min_length = min_length
        self.max_length = max_length
        self.require_punctuation = require_punctuation
    
    @property
    def name(self) -> str:
        return f"alt_text(min={self.min_length}, max={self.max_length})"
    
    @property
    def description(self) -> str:
        return "Validates alt text for accessibility"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate alt text."""
        # Extract alt text from response
        if hasattr(response, 'alt_text'):
            alt_text = response.alt_text
        elif isinstance(response, dict) and 'alt_text' in response:
            alt_text = response['alt_text']
        elif isinstance(response, str):
            alt_text = response
        else:
            return ValidationResult(
                valid=False,
                error=f"Could not extract alt text from response type: {type(response)}"
            )
        
        errors = []
        suggestions = []
        
        # Check length
        text_length = len(alt_text.strip())
        if text_length < self.min_length:
            errors.append(f"Alt text too short: {text_length} < {self.min_length} characters")
            suggestions.append("Provide more descriptive alt text")
        
        if text_length > self.max_length:
            errors.append(f"Alt text too long: {text_length} > {self.max_length} characters")
            suggestions.append(f"Shorten to under {self.max_length} characters")
        
        # Check for proper ending punctuation
        if self.require_punctuation and not alt_text.strip().endswith(('.', '!', '?')):
            errors.append("Alt text should end with punctuation")
            suggestions.append("Add period at the end")
        
        # Check for common issues
        if alt_text.lower().startswith(('image of', 'picture of', 'photo of')):
            errors.append("Alt text should not start with 'image of' or similar")
            suggestions.append("Remove redundant prefix")
        
        if errors:
            return ValidationResult(
                valid=False,
                error="; ".join(errors),
                suggestions=suggestions,
                debug_info={"length": text_length}
            )
        
        return ValidationResult(
            valid=True,
            debug_info={"length": text_length}
        )