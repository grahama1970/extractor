"""
Shared utilities for enforcing strict JSON-mode responses across steps.
"""

# Single source of truth for system guard enforcing JSON output
JSON_SYSTEM_GUARD: str = (
    "You output ONLY well-formed JSON objects. No prose, markdown, or extra text. "
    "Use double-quoted keys/strings and no trailing commas."
)

