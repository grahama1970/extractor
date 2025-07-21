"""
Compatibility layer for marker → extractor migration.
This module will be removed in version 2.0.0
"""
import warnings
warnings.warn(
    "The 'marker' package has been renamed to 'extractor'. "
    "Please update your imports to use 'from extractor import ...' instead. "
    "This compatibility layer will be removed in version 2.0.0",
    DeprecationWarning,
    stacklevel=2
)

# Re-export everything from extractor
from extractor import *