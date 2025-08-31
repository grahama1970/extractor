"""
Module: validation_strategies.py

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

from typing import Dict, List


def validate_description_length(response: Dict, messages: List[Dict]) -> bool:
    """Validate that the description is not too long."""
    if len(response.get("description", "").split()) > 30:
        messages.append({
            "role": "assistant",
            "content": "Description is too long. Keep it under 30 words."
        })
        return False
    return True

def validate_description_present(response: Dict, messages: List[Dict]) -> bool:
    """Validate that the description is present."""
    if not response.get("description"):
        messages.append({
            "role": "assistant",
            "content": "Description is missing. Please provide a description."
        })
        return False
    return True

def validate_field_type(response: Dict, messages: List[Dict]) -> bool:
    """Validate that the field type is valid."""
    valid_types = ["string", "number", "boolean", "array", "object", "date", "unknown"]
    if response.get("type") not in valid_types:
        messages.append({
            "role": "assistant",
            "content": f"Invalid field type. Must be one of: {', '.join(valid_types)}."
        })
        return False
    return True

def citation_present(response: Dict, messages: List[Dict]) -> bool:

    # make AQL call for bm25 and embbeddings and glossary items matches to narrow down results
    # Use rapidfuzz to a match that is 97% or higher for small punctuation differences
    # If failed, tell the LLM that the response does not exist in the database 
    # and ask it to try again looking more closely at the proivded database schema
    """Validate that the citation is present."""
    if not response.get("citation"):
        e = Exception("Citation is missing. Please provide a citation.")
        messages.append({
            "role": "assistant",
            "content": "Citation is missing. Please provide a citation.",
            "validation": "citation_missing",
            "status": "failed",      # success
            "errors": [f"Unexpected error: {str(e)}"],
        })
        return False
    return True

# Example list of validation strategies
VALIDATION_STRATEGIES = [
    validate_description_length,
    validate_description_present,
    validate_field_type,
]