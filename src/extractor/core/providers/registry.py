"""
Module: registry.py
Description: Functions for registry operations

External Dependencies:
- filetype: [Documentation URL]
- bs4: [Documentation URL]
- marker: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

import filetype
import filetype.match as file_match
from bs4 import BeautifulSoup
from filetype.types import archive, document, IMAGE

from extractor.core.providers.document import DocumentProvider
from extractor.core.providers.epub import EpubProvider
from extractor.core.providers.html import HTMLProvider
from extractor.core.providers.image import ImageProvider
from extractor.core.providers.pdf import PdfProvider
from extractor.core.providers.powerpoint import PowerPointProvider
from extractor.core.providers.spreadsheet import SpreadSheetProvider

DOCTYPE_MATCHERS = {
    "image": IMAGE,
    "pdf": [
        archive.Pdf,
    ],
    "epub": [
        archive.Epub,
    ],
    "doc": [document.Doc, document.Docx, document.Odt],
    "xls": [document.Xls, document.Xlsx, document.Ods],
    "ppt": [document.Ppt, document.Pptx, document.Odp],
}


def load_matchers(doctype: str):
    return [cls() for cls in DOCTYPE_MATCHERS[doctype]]


def load_extensions(doctype: str):
    return [cls.EXTENSION for cls in DOCTYPE_MATCHERS[doctype]]


def provider_from_ext(filepath: str):
    ext = filepath.rsplit(".", 1)[-1].strip()
    if not ext:
        return PdfProvider

    if ext in load_extensions("image"):
        return ImageProvider
    if ext in load_extensions("pdf"):
        return PdfProvider
    if ext in load_extensions("doc"):
        return DocumentProvider
    if ext in load_extensions("xls"):
        return SpreadSheetProvider
    if ext in load_extensions("ppt"):
        return PowerPointProvider
    if ext in load_extensions("epub"):
        return EpubProvider
    if ext in ["html"]:
        return HTMLProvider

    return PdfProvider


def provider_from_filepath(filepath: str):
    if filetype.image_match(filepath) is not None:
        return ImageProvider
    if file_match(filepath, load_matchers("pdf")) is not None:
        return PdfProvider
    if file_match(filepath, load_matchers("epub")) is not None:
        return EpubProvider
    if file_match(filepath, load_matchers("doc")) is not None:
        return DocumentProvider
    if file_match(filepath, load_matchers("xls")) is not None:
        return SpreadSheetProvider
    if file_match(filepath, load_matchers("ppt")) is not None:
        return PowerPointProvider

    try:
        soup = BeautifulSoup(open(filepath, "r").read(), "html.parser")
        # Check if there are any HTML tags
        if bool(soup.find()):
            return HTMLProvider
    except Exception:
        pass

    # Fallback if we incorrectly detect the file type
    return provider_from_ext(filepath)
