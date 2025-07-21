"""
Module: basic_usage.py

External Dependencies:
- litellm: [Documentation URL]
- pydantic: https://docs.pydantic.dev/
- marker: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

#!/usr/bin/env python3
"""Basic usage example of the LLM validation loop."""

import litellm
from litellm import completion
from pydantic import BaseModel

# Initialize caching (optional but recommended)
from extractor.core.services.utils.litellm_cache import initialize_litellm_cache
initialize_litellm_cache()

# Enable JSON schema validation
litellm.enable_json_schema_validation = True

# Define your response model
class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

# Basic usage without validation (standard litellm)
messages = [
    {"role": "system", "content": "Extract the event information."},
    {"role": "user", "content": "Alice and Bob are going to a science fair on Friday."},
]

response = completion(
    model="gemini/gemini-1.5-pro",
    messages=messages,
    response_format=CalendarEvent,
)

print("Basic response:", response)

# Enhanced usage with validation
from extractor.core.llm_call.litellm_integration import completion_with_validation

response_validated = completion_with_validation(
    model="gemini/gemini-1.5-pro",
    messages=messages,
    response_format=CalendarEvent,
    validation_strategies=[
        "field_presence(required_fields=['name', 'date', 'participants'])",
        "length_check(field_name='name', min_length=3)",
        "content_quality(min_words=1)",
    ],
    max_retries=3,
    enable_cache=True,
    debug=True  # See validation process
)

print("\nValidated response:", response_validated)