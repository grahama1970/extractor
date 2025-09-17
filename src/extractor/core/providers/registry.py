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

import filetype
import filetype.match as file_match
from pathlib import Path
from typing import Type

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
    "html": HTMLProvider,
    "htm": HTMLProvider,
    "rst": RSTProvider,
    "md": MarkdownProvider,
    "markdown": MarkdownProvider,
    # PDF remains the fallback
    "pdf": PdfProvider,
}


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
    mime = filetype.guess(str(path))
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

    # 3. HTML sniffing
    if ext in {"html", "htm"}:
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                head = f.read(2048)
            from bs4 import BeautifulSoup

            if BeautifulSoup(head, "html.parser").find():
                return HTMLProvider
        except Exception:
            pass

    # 4. Fallback
    return PdfProvider
