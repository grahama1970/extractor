"""String corpus validator for testing."""

from typing import List, Optional, Union, Any, Dict
from marker.core.llm_call.base import ValidationResult
from marker.core.llm_call.decorators import validator


@validator("string_corpus")
class StringCorpusValidator:
    """Validates that LLM response contains only strings from a provided corpus."""
    
    def __init__(self, corpus: List[str], case_sensitive: bool = False):
        """Initialize with a corpus of allowed strings.
        
        Args:
            corpus: List of allowed strings
            case_sensitive: Whether to do case-sensitive matching
        """
        self.corpus = corpus
        self.case_sensitive = case_sensitive
        if not case_sensitive:
            self.corpus = [s.lower() for s in corpus]
    
    def validate(self, response: Any, context: Optional[Dict] = None) -> ValidationResult:
        """Validate that response contains only corpus strings."""
        # Convert response to string
        response_str = str(response)
        
        # Split into words for checking
        words = response_str.split()
        
        # Check each word against corpus
        invalid_words = []
        for word in words:
            # Clean punctuation and check
            clean_word = word.strip('.,!?;:"')
            check_word = clean_word if self.case_sensitive else clean_word.lower()
            
            if check_word and check_word not in self.corpus:
                invalid_words.append(clean_word)
        
        if invalid_words:
            return ValidationResult(
                valid=False,
                error=f"Response contains words not in corpus: {', '.join(invalid_words)}",
                suggestions=[
                    f"Use only words from: {', '.join(self.corpus[:5])}{'...' if len(self.corpus) > 5 else ''}",
                    "Ensure response matches corpus requirements"
                ]
            )
        
        return ValidationResult(valid=True)