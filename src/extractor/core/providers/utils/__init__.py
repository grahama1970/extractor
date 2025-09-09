"""
Shared utilities for document providers.
"""

def alphanum_ratio(text):
    """Calculate the ratio of alphanumeric characters in text."""
    text = text.replace(" ", "")
    text = text.replace("\n", "")
    alphanumeric_count = sum([1 for c in text if c.isalnum()])

    if len(text) == 0:
        return 1

    ratio = alphanumeric_count / len(text)
    return ratio