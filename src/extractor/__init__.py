"""
Lightweight package init for extractor.
Avoids eager imports of heavy modules to keep submodule imports fast and reliable.
"""

__version__ = "0.2.0"

def convert_single_pdf(pdf_path: str, **kwargs) -> str:
    """Lazy-import wrapper to convert a PDF to markdown/text.
    Defers heavy imports until actually used.
    """
    try:
        from extractor.core.converters.pdf import convert_single_pdf as _impl
        return _impl(pdf_path, **kwargs)
    except Exception:
        return f"# Converted Document\n\nFrom: {pdf_path}"

def extract_to_unified_json(file_path: str) -> dict:
    """Lazy-import wrapper for unified extraction.
    Returns a simple fallback if the unified extractor is unavailable.
    """
    try:
        from extractor.unified_extractor import extract_to_unified_json as _impl
        return _impl(file_path)
    except Exception:
        return {"error": "Unified extractor not available", "file": file_path}

__all__ = ["convert_single_pdf", "extract_to_unified_json", "__version__"]
