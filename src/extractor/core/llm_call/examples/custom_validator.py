"""
Module: custom_validator.py

External Dependencies:
- marker: [Documentation URL]
- pydantic: https://docs.pydantic.dev/

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

#!/usr/bin/env python3
"""Example of creating and using custom validators."""

from typing import Any, Dict
from extractor.core.llm_call import validator, BaseValidator, ValidationResult
from extractor.core.llm_call.litellm_integration import completion_with_validation
from pydantic import BaseModel


# Create a custom validator
@validator("business_hours")
class BusinessHoursValidator(BaseValidator):
    """Validates that times are within business hours."""
    
    def __init__(self, start_hour: int = 9, end_hour: int = 17):
        self.start_hour = start_hour
        self.end_hour = end_hour
    
    @property
    def name(self) -> str:
        return f"business_hours({self.start_hour}-{self.end_hour})"
    
    @property
    def description(self) -> str:
        return "Validates times are within business hours"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Check if meeting times are within business hours."""
        if hasattr(response, 'time'):
            time_str = response.time
        elif isinstance(response, dict) and 'time' in response:
            time_str = response['time']
        else:
            return ValidationResult(
                valid=False,
                error="No time field found in response"
            )
        
        # Simple hour extraction (you'd want more robust parsing)
        try:
            hour = int(time_str.split(':')[0])
            if self.start_hour <= hour < self.end_hour:
                return ValidationResult(
                    valid=True,
                    debug_info={"hour": hour, "range": f"{self.start_hour}-{self.end_hour}"}
                )
            else:
                return ValidationResult(
                    valid=False,
                    error=f"Time {hour}:00 is outside business hours ({self.start_hour}-{self.end_hour})",
                    suggestions=[f"Schedule between {self.start_hour}:00 and {self.end_hour}:00"]
                )
        except Exception as e:
            return ValidationResult(
                valid=False,
                error=f"Could not parse time: {e}",
                suggestions=["Use format HH:MM"]
            )


# Another custom validator for email format
@validator("email_format")
class EmailValidator(BaseValidator):
    """Validates email addresses."""
    
    @property
    def name(self) -> str:
        return "email_format"
    
    @property
    def description(self) -> str:
        return "Validates email address format"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Check if email field contains valid email."""
        import re
        
        if hasattr(response, 'email'):
            email = response.email
        elif isinstance(response, dict) and 'email' in response:
            email = response['email']
        else:
            return ValidationResult(valid=True)  # Email is optional
        
        email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if re.match(email_pattern, email):
            return ValidationResult(valid=True)
        else:
            return ValidationResult(
                valid=False,
                error=f"Invalid email format: {email}",
                suggestions=["Use format: user@domain.com"]
            )


# Use the custom validators
class Meeting(BaseModel):
    subject: str
    time: str
    participants: list[str]
    email: str = ""


messages = [
    {"role": "system", "content": "Extract meeting information."},
    {"role": "user", "content": "Team sync at 3pm with John and Jane. Contact: john@company.com"},
]

# Use custom validators alongside built-in ones
response = completion_with_validation(
    model="gemini/gemini-1.5-pro",
    messages=messages,
    response_format=Meeting,
    validation_strategies=[
        "field_presence(required_fields=['subject', 'time', 'participants'])",
        "business_hours(start_hour=9, end_hour=17)",  # Our custom validator
        "email_format",  # Our email validator
    ],
    max_retries=3,
    debug=True
)

print("Validated meeting:", response)