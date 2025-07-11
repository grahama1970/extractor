"""General-purpose validators for LLM validation."""
Module: general.py

from typing import Any, Dict, List, Optional
import re

from extractor.core.llm_call.core.base import ValidationResult
from extractor.core.llm_call.validators.base import BaseValidator
from extractor.core.llm_call.core.strategies import validator


@validator("content_quality")
class ContentQualityValidator(BaseValidator):
    """Validates general content quality metrics."""
    
    def __init__(self,
                 min_words: Optional[int] = None,
                 max_words: Optional[int] = None,
                 forbidden_words: Optional[List[str]] = None,
                 required_sections: Optional[List[str]] = None):
        """Initialize content quality validator.
        
        Args:
            min_words: Minimum word count
            max_words: Maximum word count
            forbidden_words: Words that should not appear
            required_sections: Sections that must be present
        """
        self.min_words = min_words
        self.max_words = max_words
        self.forbidden_words = forbidden_words or []
        self.required_sections = required_sections or []
    
    @property
    def name(self) -> str:
        params = []
        if self.min_words:
            params.append(f"min_words={self.min_words}")
        if self.max_words:
            params.append(f"max_words={self.max_words}")
        if self.forbidden_words:
            params.append(f"forbidden={len(self.forbidden_words)}")
        if self.required_sections:
            params.append(f"sections={len(self.required_sections)}")
        params_str = f"({', '.join(params)})" if params else ""
        return f"content_quality{params_str}"
    
    @property
    def description(self) -> str:
        return "Validates general content quality metrics"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate content quality."""
        # Extract content from response
        if hasattr(response, 'content'):
            content = response.content
        elif isinstance(response, dict) and 'content' in response:
            content = response['content']
        elif isinstance(response, str):
            content = response
        else:
            return ValidationResult(
                valid=False,
                error=f"Could not extract content from response type: {type(response)}"
            )
        
        errors = []
        suggestions = []
        debug_info = {}
        
        # Count words
        words = content.split()
        word_count = len(words)
        debug_info["word_count"] = word_count
        
        if self.min_words and word_count < self.min_words:
            errors.append(f"Content too short: {word_count} < {self.min_words} words")
            suggestions.append(f"Expand content to at least {self.min_words} words")
        
        if self.max_words and word_count > self.max_words:
            errors.append(f"Content too long: {word_count} > {self.max_words} words")
            suggestions.append(f"Reduce content to at most {self.max_words} words")
        
        # Check forbidden words
        content_lower = content.lower()
        found_forbidden = []
        for word in self.forbidden_words:
            if word.lower() in content_lower:
                found_forbidden.append(word)
        
        if found_forbidden:
            errors.append(f"Found forbidden words: {', '.join(found_forbidden)}")
            suggestions.append("Remove inappropriate content")
            debug_info["forbidden_found"] = found_forbidden
        
        # Check required sections
        missing_sections = []
        for section in self.required_sections:
            if section.lower() not in content_lower:
                missing_sections.append(section)
        
        if missing_sections:
            errors.append(f"Missing required sections: {', '.join(missing_sections)}")
            suggestions.append(f"Add sections: {', '.join(missing_sections)}")
            debug_info["missing_sections"] = missing_sections
        
        if errors:
            return ValidationResult(
                valid=False,
                error="; ".join(errors),
                suggestions=suggestions,
                debug_info=debug_info
            )
        
        return ValidationResult(
            valid=True,
            debug_info=debug_info
        )


@validator("tone_consistency")
class ToneConsistencyValidator(BaseValidator):
    """Validates tone and style consistency."""
    
    def __init__(self,
                 expected_tone: str = "professional",
                 check_person: bool = True,
                 check_tense: bool = True):
        """Initialize tone consistency validator.
        
        Args:
            expected_tone: Expected tone (professional, casual, academic, etc.)
            check_person: Check for consistent person (first, second, third)
            check_tense: Check for consistent tense
        """
        self.expected_tone = expected_tone
        self.check_person = check_person
        self.check_tense = check_tense
    
    @property
    def name(self) -> str:
        return f"tone_consistency(tone={self.expected_tone})"
    
    @property
    def description(self) -> str:
        return "Validates tone and style consistency"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate tone consistency."""
        # Extract content from response
        if hasattr(response, 'content'):
            content = response.content
        elif isinstance(response, dict) and 'content' in response:
            content = response['content']
        elif isinstance(response, str):
            content = response
        else:
            return ValidationResult(
                valid=False,
                error=f"Could not extract content from response type: {type(response)}"
            )
        
        errors = []
        suggestions = []
        debug_info = {"expected_tone": self.expected_tone}
        
        # Tone indicators
        casual_indicators = ["wanna", "gonna", "hey", "cool", "awesome", "yeah"]
        professional_indicators = ["therefore", "furthermore", "however", "consequently"]
        academic_indicators = ["hypothesis", "methodology", "empirical", "theoretical"]
        
        content_lower = content.lower()
        
        # Check tone
        if self.expected_tone == "professional":
            casual_found = [ind for ind in casual_indicators if ind in content_lower]
            if casual_found:
                errors.append(f"Found casual language: {', '.join(casual_found)}")
                suggestions.append("Use more professional language")
                debug_info["casual_found"] = casual_found
        
        elif self.expected_tone == "casual":
            professional_found = [ind for ind in professional_indicators if ind in content_lower]
            if professional_found:
                errors.append(f"Found overly formal language: {', '.join(professional_found)}")
                suggestions.append("Use more casual, conversational tone")
                debug_info["formal_found"] = professional_found
        
        # Check person consistency
        if self.check_person:
            first_person = len(re.findall(r'\b(I|me|my|mine|we|us|our)\b', content, re.I))
            second_person = len(re.findall(r'\b(you|your|yours)\b', content, re.I))
            third_person = len(re.findall(r'\b(he|she|it|they|him|her|his|hers|their)\b', content, re.I))
            
            person_usage = {
                "first": first_person,
                "second": second_person,
                "third": third_person
            }
            debug_info["person_usage"] = person_usage
            
            # Detect inconsistent person usage
            used_persons = [p for p, count in person_usage.items() if count > 0]
            if len(used_persons) > 1:
                primary_person = max(person_usage.items(), key=lambda x: x[1])[0]
                errors.append(f"Inconsistent person usage. Primary: {primary_person}")
                suggestions.append(f"Maintain consistent {primary_person} person throughout")
        
        # Check tense consistency (simplified)
        if self.check_tense:
            past_tense = len(re.findall(r'\b(was|were|had|did|went|came|saw)\b', content, re.I))
            present_tense = len(re.findall(r'\b(is|are|have|do|go|come|see)\b', content, re.I))
            future_tense = len(re.findall(r'\b(will|shall|going to)\b', content, re.I))
            
            tense_usage = {
                "past": past_tense,
                "present": present_tense,
                "future": future_tense
            }
            debug_info["tense_usage"] = tense_usage
            
            # Detect mixed tenses
            used_tenses = [t for t, count in tense_usage.items() if count > 2]
            if len(used_tenses) > 1:
                primary_tense = max(tense_usage.items(), key=lambda x: x[1])[0]
                errors.append(f"Mixed tenses detected. Primary: {primary_tense}")
                suggestions.append(f"Maintain consistent {primary_tense} tense")
        
        if errors:
            return ValidationResult(
                valid=False,
                error="; ".join(errors),
                suggestions=suggestions,
                debug_info=debug_info
            )
        
        return ValidationResult(
            valid=True,
            debug_info=debug_info
        )


@validator("json_structure")
class JSONStructureValidator(BaseValidator):
    """Validates JSON structure and schema compliance."""
    
    def __init__(self,
                 required_keys: Optional[List[str]] = None,
                 schema: Optional[Dict[str, Any]] = None):
        """Initialize JSON structure validator.
        
        Args:
            required_keys: Keys that must be present
            schema: JSON schema to validate against
        """
        self.required_keys = required_keys or []
        self.schema = schema
    
    @property
    def name(self) -> str:
        if self.required_keys:
            return f"json_structure(keys={len(self.required_keys)})"
        return "json_structure"
    
    @property
    def description(self) -> str:
        return "Validates JSON structure and required fields"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate JSON structure."""
        # Extract JSON data from response
        if isinstance(response, dict):
            json_data = response
        elif hasattr(response, '__dict__'):
            json_data = response.__dict__
        else:
            try:
                import json
                json_data = json.loads(str(response))
            except:
                return ValidationResult(
                    valid=False,
                    error=f"Could not extract JSON from response type: {type(response)}"
                )
        
        errors = []
        suggestions = []
        debug_info = {"keys_found": list(json_data.keys())}
        
        # Check required keys
        missing_keys = []
        for key in self.required_keys:
            if key not in json_data:
                missing_keys.append(key)
        
        if missing_keys:
            errors.append(f"Missing required keys: {', '.join(missing_keys)}")
            suggestions.append(f"Add missing keys: {', '.join(missing_keys)}")
            debug_info["missing_keys"] = missing_keys
        
        # Validate against schema if provided
        if self.schema:
            try:
                import jsonschema
                jsonschema.validate(json_data, self.schema)
            except jsonschema.ValidationError as e:
                errors.append(f"Schema validation failed: {e.message}")
                suggestions.append("Fix JSON structure to match schema")
                debug_info["schema_error"] = str(e)
            except ImportError:
                errors.append("jsonschema library required for schema validation")
                suggestions.append("Install jsonschema: pip install jsonschema")
        
        if errors:
            return ValidationResult(
                valid=False,
                error="; ".join(errors),
                suggestions=suggestions,
                debug_info=debug_info
            )
        
        return ValidationResult(
            valid=True,
            debug_info=debug_info
        )