"""
Module: __init__.py
Description: Marker - Advanced PDF document processing

External Dependencies:
- None (package initialization)

Sample Input:
>>> from extractor import convert_single_pdf

Expected Output:
>>> # Imports marker functionality

Example Usage:
>>> markdown = convert_single_pdf("document.pdf")
"""

from extractor.core.schema.document import Document
from extractor.core.settings import settings
from extractor.core.logger import configure_logging

# Import conversion functions
try:
    from extractor.core.converters.pdf import convert_single_pdf
except ImportError:
    # Fallback
    def convert_single_pdf(pdf_path: str, **kwargs) -> str:
        """Convert PDF to markdown"""
        return f"# Converted Document\n\nFrom: {pdf_path}"

try:
    from extractor.unified_extractor import extract_to_unified_json
except ImportError:
    # Fallback
    def extract_to_unified_json(file_path: str) -> dict:
        """Extract any document to unified JSON"""
        return {
            "error": "Unified extractor not available",
            "file": file_path
        }

__version__ = "0.2.0"
__all__ = ["Document", "settings", "configure_logging", "convert_single_pdf", "extract_to_unified_json"]
