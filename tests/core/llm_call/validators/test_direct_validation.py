#!/usr/bin/env python3
"""Demonstrate validation failure when a value is not in an allowed set."""

from typing import Dict, List, Any, Optional


class ValidationResult:
    """Result of a validation check."""
    
    def __init__(self, valid: bool, error: str = None, suggestions: List[str] = None, debug_info: Dict = None):
        self.valid = valid
        self.error = error
        self.suggestions = suggestions or []
        self.debug_info = debug_info or {}


class SimpleValidator:
    """Simple validator that checks if a value is in an allowed list."""
    
    def __init__(self, allowed_values: List[str], case_sensitive: bool = False):
        self.allowed_values = allowed_values
        self.case_sensitive = case_sensitive
        if not case_sensitive:
            self.allowed_values = [v.lower() for v in allowed_values]
    
    def validate(self, response: Any, context: Optional[Dict] = None) -> ValidationResult:
        """Validate that response is in allowed values."""
        # Convert response to string
        response_str = str(response)
        
        # Check with case sensitivity as configured
        check_value = response_str if self.case_sensitive else response_str.lower()
        
        # Check if response is in allowed values
        if check_value not in self.allowed_values:
            return ValidationResult(
                valid=False,
                error=f"Response '{response_str}' not in allowed values: {', '.join(self.allowed_values)}"
            )
        
        return ValidationResult(valid=True)


def main():
    """Test the validation with a simple example."""
    # Create validator with three cities
    validator = SimpleValidator(['London', 'Houston', 'New York City'])
    
    # Test with 'Paris' - should fail
    result = validator.validate('Paris', {})
    
    print(f"Validating 'Paris' against allowed values: {validator.allowed_values}")
    print(f"Valid: {result.valid}")
    if not result.valid:
        print(f"Error: {result.error}")
    
    # Test with 'London' - should pass
    result = validator.validate('London', {})
    print(f"\nValidating 'London' against allowed values: {validator.allowed_values}")
    print(f"Valid: {result.valid}")


if __name__ == "__main__":
    main()