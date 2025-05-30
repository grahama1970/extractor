"""Value validators for testing."""

from typing import Any, Dict, List, Optional
from marker.core.llm_call.base import ValidationResult
from marker.core.llm_call.decorators import validator


@validator("value_in_list")
class ValueInListValidator:
    """Validates that a response contains only values from an allowed list."""
    
    def __init__(self, allowed_values: List[str], case_sensitive: bool = False):
        """Initialize validator.
        
        Args:
            allowed_values: List of allowed values
            case_sensitive: Whether to do case-sensitive matching
        """
        self.allowed_values = allowed_values
        self.case_sensitive = case_sensitive
        if not case_sensitive:
            self.allowed_values = [v.lower() for v in allowed_values]
    
    @property
    def name(self) -> str:
        return f"value_in_list({','.join(self.allowed_values[:3])}{'...' if len(self.allowed_values) > 3 else ''})"
    
    def validate(self, response: Any, context: Optional[Dict] = None) -> ValidationResult:
        """Validate response value."""
        # Convert response to string
        response_str = str(response)
        
        # Check if case sensitive
        check_value = response_str if self.case_sensitive else response_str.lower()
        
        # Check if response is in allowed values
        if check_value not in self.allowed_values:
            return ValidationResult(
                valid=False,
                error=f"Response '{response_str}' not in allowed values",
                suggestions=[
                    f"Use one of the allowed values: {', '.join(self.allowed_values[:5])}{'...' if len(self.allowed_values) > 5 else ''}"
                ]
            )
        
        return ValidationResult(valid=True)