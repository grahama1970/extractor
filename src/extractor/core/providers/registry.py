"""
Module: registry.py
Description: Provider factory for native (loss-free) extraction only.

External Dependencies:
- filetype: https://pypi.org/project/filetype/
- bs4:      https://pypi.org/project/beautifulsoup4/

Example usage
-------------
>>> from extractor.core.providers.registry import provider_from_filepath
>>> provider_class = provider_from_filepath("report.docx")
>>> doc = provider_class("report.docx").extract_document()
"""

import os

try:
    import filetype  # type: ignore
except Exception:  # pragma: no cover
    filetype = None  # type: ignore
from pathlib import Path
from typing import Type
from loguru import logger

# --- Native providers -------------------------------------------------
from extractor.core.providers.image import ImageProvider
from extractor.core.providers.pdf import PdfProvider
from extractor.core.providers.docx import DOCXProvider
from extractor.core.providers.epub import EPUBProvider
from extractor.core.providers.html import HTMLProvider
from extractor.core.providers.pptx import PPTXProvider
from extractor.core.providers.rst import RSTProvider
from extractor.core.providers.spreadsheet import SpreadsheetProvider
from extractor.core.providers.markdown import MarkdownProvider
from extractor.core.providers.xml import XMLProvider
from extractor.core.providers.xml import XMLProvider
from extractor.core.providers.reqif import ReqIFProvider
from extractor.core.providers.txt import TXTProvider
from extractor.core.providers.json import JSONProvider
# Try to import Schematron provider — used as enhancement, NOT replacement
try:
    from extractor.pipeline.ingest.schematron_provider import SchematronHTMLProvider
except ImportError as e:
    logger.debug(f"SchematronHTMLProvider not available: {e}")
    SchematronHTMLProvider = None

# ------------------------------------------------------------------
# Provider factory
# ------------------------------------------------------------------
_PROVIDER_MAP: dict[str, Type] = {
    # images
    "png": ImageProvider,
    "jpg": ImageProvider,
    "jpeg": ImageProvider,
    "gif": ImageProvider,
    "bmp": ImageProvider,
    "tiff": ImageProvider,
    "svg": ImageProvider,
    "webp": ImageProvider,
    # documents (native extraction)
    "docx": DOCXProvider,
    "doc": DOCXProvider,
    "odt": DOCXProvider,
    "xlsx": SpreadsheetProvider,
    "xls": SpreadsheetProvider,
    "xlsm": SpreadsheetProvider,
    "ods": SpreadsheetProvider,
    "pptx": PPTXProvider,
    "ppt": PPTXProvider,
    "odp": PPTXProvider,
    "epub": EPUBProvider,
    "epub": EPUBProvider,
    "xml": XMLProvider,
    "html": HTMLProvider,  # Will be overridden if Schematron is available
    "htm": HTMLProvider,
    "rst": RSTProvider,
    "rst": RSTProvider,
    "md": MarkdownProvider,
    "markdown": MarkdownProvider,
    "txt": TXTProvider,
    "text": TXTProvider,  # Also support .text extension
    "log": TXTProvider,
    "c": TXTProvider,
    "h": TXTProvider,
    "cpp": TXTProvider,
    "py": TXTProvider,
    "java": TXTProvider,
    "csv": SpreadsheetProvider,
    "tsv": SpreadsheetProvider,
    "json": JSONProvider,
    "jsonl": JSONProvider,  # JSON Lines format
    "reqif": ReqIFProvider,
    "reqifz": ReqIFProvider,
    # PDF remains the fallback
    "pdf": PdfProvider,
}

# Schematron enhances HTML extraction but NEVER replaces it.
# If Schematron fails (API down, bad output), we fall back to native HTMLProvider.
# The registry maps to a wrapper that handles this fallback chain.
if SchematronHTMLProvider:

    class _SchematronWithFallback:
        """Tries SchematronHTMLProvider first, falls back to native HTMLProvider.

        This wrapper ensures HTML extraction NEVER fails just because
        the SGLang API is unavailable or the model returns bad output.

        Set EXTRACT_HTML_SKIP_LLM=1 to bypass Schematron entirely (e.g. batch/offline).
        """

        def __init__(self, config=None):
            self._schematron = SchematronHTMLProvider(config=config)
            self._fallback = HTMLProvider(config=config)

        def extract_document(self, filepath):
            if os.environ.get("EXTRACT_HTML_SKIP_LLM", "") == "1":
                return self._fallback.extract_document(filepath)
            try:
                return self._schematron.extract_document(filepath)
            except ConnectionError as e:
                logger.warning(f"Schematron unavailable, falling back to HTMLProvider: {e}")
                return self._fallback.extract_document(filepath)
            except RuntimeError as e:
                logger.warning(f"Schematron failed after retries, falling back to HTMLProvider: {e}")
                return self._fallback.extract_document(filepath)
            except Exception as e:
                logger.error(f"Unexpected Schematron error ({type(e).__name__}: {e}), falling back to HTMLProvider")
                return self._fallback.extract_document(filepath)

    _PROVIDER_MAP["html"] = _SchematronWithFallback
    _PROVIDER_MAP["htm"] = _SchematronWithFallback


def provider_from_filepath(filepath: str) -> Type:
    """
    Return the *native* provider class for the given file path.

    Priority:
    1. Exact extension match in `_PROVIDER_MAP`.
    2. MIME type detection via `filetype`.
    3. HTML heuristics (if file looks like HTML).
    4. Fallback to `PdfProvider`.
    """
    path = Path(filepath)

    # 1. Exact extension
    ext = path.suffix.lower().lstrip(".")
    if ext in _PROVIDER_MAP:
        return _PROVIDER_MAP[ext]

    # 2. MIME detection
    mime = filetype.guess(str(path)) if filetype is not None else None
    if mime and hasattr(mime, "mime"):
        mime_map = {
            "image": ImageProvider,
            "application/pdf": PdfProvider,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DOCXProvider,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": SpreadsheetProvider,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": PPTXProvider,
            "application/epub+zip": EPUBProvider,
            "application/vnd.oasis.opendocument.text": DOCXProvider,
            "application/vnd.oasis.opendocument.spreadsheet": SpreadsheetProvider,
            "application/vnd.oasis.opendocument.presentation": PPTXProvider,
        }
        # Handle image MIME types that start with "image/"
        if mime.mime.startswith("image/"):
            return ImageProvider

        provider = mime_map.get(mime.mime)
        if provider:
            return provider

    # 3. HTML sniffing (for files without .html/.htm extension)
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            head = f.read(2048)
        from bs4 import BeautifulSoup

        if BeautifulSoup(head, "html.parser").find():
            # Use the fallback-wrapped provider if available, else native
            return _PROVIDER_MAP.get("html", HTMLProvider)
    except Exception as e:
        logger.debug(f"HTML sniffing failed for {filepath}: {e}")

    # 4. Fallback
    return PdfProvider
