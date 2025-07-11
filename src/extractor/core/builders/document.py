"""
Module: document.py

External Dependencies:
- marker: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

from typing import Annotated

from extractor.core.builders import BaseBuilder
from extractor.core.builders.layout import LayoutBuilder
from extractor.core.builders.line import LineBuilder
from extractor.core.builders.ocr import OcrBuilder
from extractor.core.providers.pdf import PdfProvider
from extractor.core.schema import BlockTypes
from extractor.core.schema.document import Document
from extractor.core.schema.groups.page import PageGroup
from extractor.core.schema.registry import get_block_class


class DocumentBuilder(BaseBuilder):
    """
    Constructs a Document given a PdfProvider, LayoutBuilder, and OcrBuilder.
    """
    lowres_image_dpi: Annotated[
        int,
        "DPI setting for low-resolution page images used for Layout and Line Detection.",
    ] = 96
    highres_image_dpi: Annotated[
        int,
        "DPI setting for high-resolution page images used for OCR.",
    ] = 192
    disable_ocr: Annotated[
        bool,
        "Disable OCR processing.",
    ] = False

    def __call__(self, provider: PdfProvider, layout_builder: LayoutBuilder, line_builder: LineBuilder, ocr_builder: OcrBuilder):
        document = self.build_document(provider)
        layout_builder(document, provider)
        line_builder(document, provider)
        if not self.disable_ocr:
            ocr_builder(document, provider)
        return document

    def build_document(self, provider: PdfProvider):
        PageGroupClass: PageGroup = get_block_class(BlockTypes.Page)
        lowres_images = provider.get_images(provider.page_range, self.lowres_image_dpi)
        highres_images = provider.get_images(provider.page_range, self.highres_image_dpi)
        initial_pages = [
            PageGroupClass(
                page_id=p,
                lowres_image=lowres_images[i],
                highres_image=highres_images[i],
                polygon=provider.get_page_bbox(p),
                refs=provider.get_page_refs(p)
            ) for i, p in enumerate(provider.page_range)
        ]
        DocumentClass: Document = get_block_class(BlockTypes.Document)
        return DocumentClass(filepath=provider.filepath, pages=initial_pages)
