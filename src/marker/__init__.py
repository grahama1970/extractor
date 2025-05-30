"""Marker - Advanced PDF document processing with optional AI-powered accuracy improvements."""

# Import core functionality
from marker.core.schema.document import Document
from marker.core.settings import settings
from marker.core.logger import configure_logging

# Import main conversion function
try:
    from marker.core.converters import convert_single_pdf
except ImportError:
    # Handle import gracefully during restructuring
    pass

__version__ = "0.2.0"
__all__ = ["Document", "settings", "configure_logging", "convert_single_pdf"]
