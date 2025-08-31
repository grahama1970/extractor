"""
Module: litellm_validation_example.py
Description: Large Language Model integration and management

External Dependencies:
- litellm: https://docs.litellm.ai/
- pydantic: https://docs.pydantic.dev/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

#!/usr/bin/env python3
"""
Example of LiteLLM with validation loop, following the user's provided pattern.'
This demonstrates both basic caching and validation capabilities.
"""

import litellm
import os
from litellm import completion
from pydantic import BaseModel
from marker.services.utils.litellm_cache import initialize_litellm_cache

# Initialize Redis caching
initialize_litellm_cache()

messages = [
    {"role": "system", "content": "Extract the event information."},
    {"role": "user", "content": "Alice and Bob are going to a science fair on Friday."},
]

litellm.enable_json_schema_validation = True

class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

# First call - will miss cache
print("Making first call (cache miss expected)...")
resp = completion(
    model="gemini/gemini-1.5-pro",
    messages=messages,
    response_format=CalendarEvent,
)

print("Received={}".format(resp))

# Second call - should hit cache
print("\nMaking second call (cache hit expected)...")
resp2 = completion(
    model="gemini/gemini-1.5-pro",
    messages=messages,
    response_format=CalendarEvent,
)

# Check if it was a cache hit
cache_hit = getattr(resp2, "_hidden_params", {}).get("cache_hit")
print(f"Second call cache hit: {cache_hit}")

# Now demonstrate with validation
print("\n" + "="*50)
print("Now testing with validation loop...")

from marker.llm_call.litellm_integration import completion_with_validation

# Call with custom validators
resp3 = completion_with_validation(
    model="gemini/gemini-1.5-pro",
    messages=messages,
    response_format=CalendarEvent,
    validation_strategies=[
        "field_presence(required_fields=['name', 'date', 'participants'])",
        "length_check(field_name='name', min_length=1)",
    ],
    max_retries=3,
    enable_cache=True,
    debug=True  # Enable debug mode to see validation process
)

print("\nValidated response:")
print(resp3)

# Example with a failing validation
print("\n" + "="*50)
print("Testing with validation that will likely fail...")

strict_messages = [
    {"role": "system", "content": "Extract the event information."},
    {"role": "user", "content": "Something happened."},  # Vague content
]

try:
    resp4 = completion_with_validation(
        model="gemini/gemini-1.5-pro",
        messages=strict_messages,
        response_format=CalendarEvent,
        validation_strategies=[
            "field_presence(required_fields=['name', 'date', 'participants'])",
            "content_quality(min_words=5)",  # Will fail on short responses
        ],
        max_retries=2,  # Limited retries
        enable_cache=True,
        debug=True
    )
    print("\nValidated response:")
    print(resp4)
except Exception as e:
    print(f"\nValidation failed after retries: {e}")

# Example with the enhanced service
print("\n" + "="*50)
print("Testing with EnhancedLiteLLMService...")

from marker.services.litellm_enhanced import create_enhanced_litellm_service
from marker.schema.blocks import Block
from PIL import Image

# Create a dummy image
dummy_image = Image.new('RGB', (100, 100), color='red')
dummy_block = Block()

# Create service with validation enabled
service = create_enhanced_litellm_service({
    "enable_validation_loop": True,
    "validation_strategies": [
        "field_presence(required_fields=['name', 'date', 'participants'])"
    ],
    "litellm_model": "gemini/gemini-1.5-pro",
})

# Use the service
result = service(
    prompt="Extract event information: Alice and Bob are going to a science fair on Friday.",
    image=dummy_image,
    block=dummy_block,
    response_schema=CalendarEvent
)

print("\nEnhanced service result:")
print(result)